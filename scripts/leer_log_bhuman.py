"""Lee un log binario de B-Human (el que escribe el Logger en el robot, /home/nao/logs/*.log) sin compilar nada.

Sigue el formato de bhuman/Src/Libs/Python/Logs/Log.cpp y bhuman/Src/Libs/Streaming/TypeInfo.cpp:
  [4 settings] [2 nombres de mensajes] [3 TypeInfo] [0 cola sin comprimir | 1 bloques snappy] -> mensajes
Cada mensaje: 1 byte de id + 3 bytes de tamano + datos. Los datos se decodifican con el TypeInfo del propio log
(clases, enums, arreglos T[N], std::vector<T>, primitivos), asi que no hay que adivinar la estructura.

Uso:
    uv run python scripts/leer_log_bhuman.py data/real/sesion_01/loki_CopaNAORace_1.log            # resumen
    uv run python scripts/leer_log_bhuman.py <log> --tipos JointRequest JointSensorData --json salida.json
"""
import argparse
import json
import struct
import sys
from pathlib import Path

PRIMITIVOS = {
    "bool": ("<?", 1), "char": ("<b", 1), "signed char": ("<b", 1), "unsigned char": ("<B", 1),
    "short": ("<h", 2), "unsigned short": ("<H", 2), "int": ("<i", 4), "unsigned int": ("<I", 4),
    "unsigned": ("<I", 4), "long long": ("<q", 8), "unsigned long long": ("<Q", 8), "float": ("<f", 4),
    "double": ("<d", 8), "int8_t": ("<b", 1), "uint8_t": ("<B", 1), "int16_t": ("<h", 2), "uint16_t": ("<H", 2),
    "int32_t": ("<i", 4), "uint32_t": ("<I", 4), "int64_t": ("<q", 8), "uint64_t": ("<Q", 8),
    "std::int8_t": ("<b", 1), "std::uint8_t": ("<B", 1), "std::int16_t": ("<h", 2), "std::uint16_t": ("<H", 2),
    "std::int32_t": ("<i", 4), "std::uint32_t": ("<I", 4), "std::int64_t": ("<q", 8), "std::uint64_t": ("<Q", 8),
    "long": ("<q", 8), "unsigned long": ("<Q", 8), "size_t": ("<Q", 8), "std::size_t": ("<Q", 8),
    "Angle": ("<f", 4),                    # B-Human: Angle es un float en radianes
}


class Lector:
    def __init__(self, datos, pos=0):
        self.d, self.p = datos, pos

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v

    def texto(self):
        n = self.u32(); v = self.d[self.p:self.p + n].decode("utf-8", "replace"); self.p += n; return v


def snappy_descomprimir(b):
    """Descompresor snappy en Python puro (formato crudo, sin marcos)."""
    p, largo, desp = 0, 0, 0
    while True:
        c = b[p]; p += 1
        largo |= (c & 0x7F) << desp
        if c < 0x80:
            break
        desp += 7
    out = bytearray()
    while p < len(b):
        tag = b[p]; p += 1
        t = tag & 3
        if t == 0:
            n = tag >> 2
            if n >= 60:
                k = n - 59
                n = int.from_bytes(b[p:p + k], "little"); p += k
            n += 1
            out += b[p:p + n]; p += n
            continue
        if t == 1:
            n = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | b[p]; p += 1
        elif t == 2:
            n = (tag >> 2) + 1
            off = int.from_bytes(b[p:p + 2], "little"); p += 2
        else:
            n = (tag >> 2) + 1
            off = int.from_bytes(b[p:p + 4], "little"); p += 4
        ini = len(out) - off
        for i in range(n):
            out.append(out[ini + i])
    assert len(out) == largo, (len(out), largo)
    return bytes(out)


class Log:
    def __init__(self, ruta):
        d = Path(ruta).read_bytes()
        r = Lector(d)
        magia = r.u8()
        self.settings = {}
        if magia == 4:
            version = r.u32()
            assert version == 1, version
            self.settings = dict(head=r.texto(), body=r.texto(), player=r.i32(), location=r.texto(), scenario=r.texto())
            magia = r.u8()
        assert magia == 2, "sin seccion de ids de mensajes"
        n = r.u8()
        self.ids = [r.texto() for _ in range(n)]
        magia = r.u8()
        assert magia == 3, "sin TypeInfo"
        n = r.u32() & 0x7FFFFFFF
        self.primitivos = {r.texto() for _ in range(n)}
        self.clases = {}
        for _ in range(r.u32()):
            nombre = r.texto()
            self.clases[nombre] = [(r.texto(), r.texto()) for _ in range(r.u32())]   # (nombre, tipo)
        self.enums = {}
        for _ in range(r.u32()):
            nombre = r.texto()
            self.enums[nombre] = [r.texto() for _ in range(r.u32())]
        magia = r.u8()
        if magia == 0:
            tam_bajo, resto = struct.unpack_from("<II", d, r.p); r.p += 8
            self.cola = d[r.p:]
        elif magia == 1:
            partes = []
            while r.p < len(d):
                n = r.u32()
                if n == 0:
                    break
                partes.append(snappy_descomprimir(d[r.p:r.p + n])); r.p += n
            self.cola = b"".join(partes)
        else:
            raise ValueError("formato de cola desconocido %d" % magia)

    def mensajes(self):
        """(nombre_del_id, bytes) de cada mensaje de la cola."""
        p, c = 0, self.cola
        while p + 4 <= len(c):
            cab = struct.unpack_from("<I", c, p)[0]; p += 4
            i, n = cab & 0xFF, cab >> 8
            yield (self.ids[i] if i < len(self.ids) else "id%d" % i), c[p:p + n]
            p += n

    def leer(self, tipo, r):
        tipo = tipo.strip()
        if tipo in PRIMITIVOS:
            fmt, n = PRIMITIVOS[tipo]
            v = struct.unpack_from(fmt, r.d, r.p)[0]; r.p += n; return v
        if tipo in ("std::string", "std::basic_string<char>"):
            return r.texto()
        if tipo in self.enums:
            i = r.u8()                         # B-Human guarda los enums en 1 byte
            return self.enums[tipo][i] if i < len(self.enums[tipo]) else i
        if tipo.endswith("]") and "[" in tipo:
            base, n = tipo[:tipo.rindex("[")], int(tipo[tipo.rindex("[") + 1:-1])
            return [self.leer(base, r) for _ in range(n)]
        if tipo.startswith("std::vector<") or tipo.startswith("std::list<"):
            base = tipo[tipo.index("<") + 1:tipo.rindex(">")].split(",std::allocator")[0]
            return [self.leer(base, r) for _ in range(r.u32())]
        if tipo in self.clases:
            return {nombre: self.leer(t, r) for nombre, t in self.clases[tipo]}
        if tipo.startswith("std::array<"):
            base, n = tipo[len("std::array<"):-1].rsplit(",", 1)
            return [self.leer(base, r) for _ in range(int(n))]
        raise KeyError("tipo desconocido: " + tipo)

    def decodificar(self, nombre_id, datos):
        tipo = nombre_id[2:] if nombre_id.startswith("id") else nombre_id
        return self.leer(tipo, Lector(datos))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--tipos", nargs="*", default=None, help="representaciones a extraer")
    ap.add_argument("--json", default=None, help="guardar lo extraido por hilo y cuadro")
    a = ap.parse_args()
    log = Log(a.log)
    print("settings:", log.settings)
    conteo, salida, hilo, cuadro = {}, [], None, None
    for nombre, datos in log.mensajes():
        conteo[nombre] = conteo.get(nombre, 0) + 1
        if nombre == "idFrameBegin":
            hilo = Lector(datos).texto(); cuadro = {"hilo": hilo}
        elif nombre == "idFrameFinished":
            if cuadro and len(cuadro) > 1:
                salida.append(cuadro)
            cuadro = None
        elif a.tipos is not None and nombre[2:] in a.tipos and cuadro is not None:
            cuadro[nombre[2:]] = log.decodificar(nombre, datos)
    print("mensajes:", {k: v for k, v in sorted(conteo.items(), key=lambda kv: -kv[1])})
    if a.json:
        Path(a.json).write_text(json.dumps(salida), encoding="utf-8")
        print("guardado", a.json, len(salida), "cuadros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
