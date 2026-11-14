"""Versiones por capas (leyes_mx/versiones.py, diferenciar.py, store, temas, validar, empaquetado) sobre un árbol sintético."""
import importlib.util
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
from leyes_mx import diferenciar, store, temas, versiones  # noqa: E402
import arbol_capas as A  # noqa: E402


def cargar_script(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validar = cargar_script("validar")
empaquetar = cargar_script("empaquetar_datos")

FUENTE = {"decreto": "DOF 2026-12-31", "nota": "Decreto de prueba", "fecha_dof": "2026-12-31"}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.raiz = self.tmp / "repo"
        A.arbol_base(self.raiz)
        self.dx, self.dy = A.completo_2027(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def capa_x(self, **kw):
        return diferenciar.escribir_capa(self.raiz, "XLEY", 2027, self.dx, vigente_desde="2027-01-01", fuente=FUENTE, **kw)

    def capa_y(self):
        return diferenciar.escribir_capa(self.raiz, "YLEY", 2027, self.dy, vigente_desde="2027-01-01")

    def ruta(self, anio, sigla="XLEY"):
        return self.raiz / "leyes" / str(anio) / sigla


class TestEscribirCapa(Base):
    def test_solo_guarda_lo_que_cambia(self):
        r = self.capa_x()
        self.assertEqual(r["modificados"], ["3", "4"])
        self.assertEqual(r["nuevos"], ["4-G"])
        self.assertEqual(r["derogados"], ["4"])
        self.assertEqual(r["sin_cambios"], 3)  # 1 (solo espacios), 2 y 4-F
        self.assertEqual(sorted(p.name for p in self.ruta(2027).iterdir()),
                         sorted(["_indice.md", "_meta.json", "art-0003.md", "art-0004.md", "art-0004-G.md"]))  # sin transitorios: no cambiaron

    def test_meta_de_la_capa(self):
        self.capa_x()
        m = json.loads((self.ruta(2027) / "_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(m["hereda_de"], 2026)
        self.assertEqual(m["vigente_desde"], "2027-01-01")
        self.assertEqual(m["articulos_modificados"], ["3", "4", "4-G"])
        self.assertEqual(m["articulos_nuevos"], ["4-G"])
        self.assertEqual(m["fuente"], FUENTE)
        self.assertEqual(m["articulos_extraidos"], 6)  # total de la vista, no el delta
        self.assertEqual(m["sha256_pdf"], A.SHA27)
        self.assertNotIn("vigente_hasta", m)

    def test_derogado_es_un_archivo_no_una_ausencia(self):
        self.capa_x()
        txt = (self.ruta(2027) / "art-0004.md").read_text(encoding="utf-8")
        self.assertIn('estatus: "derogado"', txt)

    def test_ley_sin_cambios_queda_solo_con_meta(self):
        r = self.capa_y()
        self.assertEqual(r["modificados"] + r["nuevos"], [])
        self.assertEqual([p.name for p in self.ruta(2027, "YLEY").iterdir()], ["_meta.json"])
        v = versiones.vista(self.raiz, "YLEY", 2027)
        self.assertEqual(v.ids(), ["1", "2"])

    def test_articulo_faltante_en_el_texto_nuevo_se_rechaza(self):
        (self.dx / "art-0004-F.md").unlink()
        with self.assertRaisesRegex(ValueError, "no están en el texto nuevo"):
            self.capa_x()
        self.assertFalse(self.ruta(2027).exists())

    def test_vigente_desde_invalido_o_no_posterior(self):
        for malo in ("2027-13-01", "enero", "2026-01-01", "2025-06-01"):
            with self.assertRaises(ValueError, msg=malo):
                diferenciar.escribir_capa(self.raiz, "XLEY", 2027, self.dx, vigente_desde=malo)

    def test_dry_run_no_escribe(self):
        r = self.capa_x(dry_run=True)
        self.assertEqual(r["nuevos"], ["4-G"])
        self.assertFalse(self.ruta(2027).exists())

    def test_regenerar_es_idempotente(self):
        self.capa_x()
        antes = {p.name: p.read_bytes() for p in self.ruta(2027).iterdir()}
        self.capa_x()
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.ruta(2027).iterdir()})

    def test_transitorios_distintos_se_guardan(self):
        A._transitorios(self.dx, "XLEY", 2027, A.SHA27, texto="Primero. Entra en vigor. Segundo. Nuevo transitorio.")
        r = self.capa_x()
        self.assertTrue(r["transitorios"])
        self.assertTrue((self.ruta(2027) / "transitorios.md").exists())
        self.assertIn("Nuevo transitorio", versiones.vista(self.raiz, "XLEY", 2027).archivo("transitorios.md").read_text(encoding="utf-8"))
        self.assertNotIn("Nuevo transitorio", versiones.vista(self.raiz, "XLEY", 2026).archivo("transitorios.md").read_text(encoding="utf-8"))


class TestVista(Base):
    def setUp(self):
        super().setUp()
        self.capa_x()
        self.capa_y()

    def test_cadena_y_orden_de_capas(self):
        self.assertEqual([c.anio for c in versiones.cadena(self.raiz, "XLEY", 2027)], [2027, 2026])
        self.assertEqual([c.anio for c in versiones.cadena(self.raiz, "XLEY", 2026)], [2026])
        self.assertEqual([c.anio for c in versiones.capas(self.raiz, "xley")], [2026, 2027])  # sigla sin distinguir mayúsculas
        self.assertEqual(versiones.cadena(self.raiz, "XLEY", 2030), [])

    def test_orden_por_vigente_desde_y_no_por_nombre_de_carpeta(self):
        # una capa con carpeta "2027" pero fecha anterior a la de otra carpeta "2028" ordena por la fecha
        meta = self.ruta(2027) / "_meta.json"
        m = json.loads(meta.read_text(encoding="utf-8"))
        m["vigente_desde"] = "2029-01-01"
        meta.write_text(json.dumps(m), encoding="utf-8")
        d28 = self.raiz / "leyes" / "2028" / "XLEY"
        d28.mkdir(parents=True)
        (d28 / "_meta.json").write_text(json.dumps({**m, "vigente_desde": "2028-01-01", "hereda_de": 2026, "articulos_modificados": []}), encoding="utf-8")
        self.assertEqual([c.anio for c in versiones.capas(self.raiz, "XLEY")], [2026, 2028, 2027])

    def test_sin_cambios_resuelve_a_la_base(self):
        for id_ in ("1", "2", "4-F"):
            self.assertEqual(versiones.resolver_articulo(self.raiz, "XLEY", 2027, id_).parent, self.ruta(2026), id_)

    def test_modificado_derogado_y_nuevo_resuelven_a_la_capa(self):
        for id_ in ("3", "4", "4-G"):
            self.assertEqual(versiones.resolver_articulo(self.raiz, "XLEY", 2027, id_).parent, self.ruta(2027), id_)

    def test_la_base_no_cambia(self):
        self.assertEqual(versiones.vista(self.raiz, "XLEY", 2026).ids(), ["1", "2", "3", "4", "4-F"])
        self.assertIsNone(versiones.resolver_articulo(self.raiz, "XLEY", 2026, "4-G"))
        self.assertIn("Texto viejo", versiones.resolver_articulo(self.raiz, "XLEY", 2026, "3").read_text(encoding="utf-8"))

    def test_ids_en_orden_de_ley(self):
        self.assertEqual(versiones.vista(self.raiz, "XLEY", 2027).ids(), ["1", "2", "3", "4", "4-F", "4-G"])

    def test_vigente_hasta_se_deriva(self):
        self.assertEqual(versiones.vigente_hasta(self.raiz, "XLEY", 2026, "3"), "2027-01-01")
        self.assertIsNone(versiones.vigente_hasta(self.raiz, "XLEY", 2026, "1"))  # nunca lo reemplaza otra capa
        self.assertIsNone(versiones.vigente_hasta(self.raiz, "XLEY", 2027, "3"))

    def test_indice_completo_con_enlaces_a_la_capa_de_origen(self):
        idx = (self.ruta(2027) / "_indice.md").read_text(encoding="utf-8").splitlines()
        orden = [l.split("|")[1].strip() for l in idx if l.startswith("| ") and not l.startswith("| Art")]
        self.assertEqual(orden, ["1", "2", "3", "4", "4-F", "4-G"])
        texto = "\n".join(idx)
        self.assertIn("[art-0001.md](../../2026/XLEY/art-0001.md)", texto)
        self.assertIn("[art-0003.md](art-0003.md)", texto)
        self.assertIn("[art-0004-G.md](art-0004-G.md)", texto)
        self.assertIn("[Transitorios](../../2026/XLEY/transitorios.md)", texto)

    def test_siglas_y_anios(self):
        self.assertEqual(versiones.siglas(self.raiz, 2027), ["XLEY", "YLEY"])
        self.assertEqual(versiones.anios(self.raiz), [2026, 2027])


class TestStore(Base):
    def setUp(self):
        super().setUp()
        self.capa_x()
        self.capa_y()

    def art(self, id_, anio):
        return store.obtener_articulo("XLEY", id_, anio=anio, raiz=self.raiz)

    def test_heredado_se_presenta_con_el_anio_pedido(self):
        f = self.art("1", 2027)
        self.assertEqual(f["anio_vigencia"], 2027)
        self.assertEqual(f["ultima_reforma_dof"], "2026-12-31")
        self.assertEqual(f["ruta"], "leyes/2026/XLEY/art-0001.md")  # el archivo real
        self.assertEqual(self.art("1", 2026)["anio_vigencia"], 2026)
        self.assertEqual(self.art("1", 2026)["ultima_reforma_dof"], "2024-04-01")

    def test_modificado_derogado_nuevo(self):
        self.assertIn("35%", self.art("3", 2027)["texto"])
        self.assertIn("30%", self.art("3", 2026)["texto"])
        self.assertEqual(self.art("4", 2027)["estatus"], "derogado")
        self.assertEqual(self.art("4", 2026)["estatus"], "vigente")
        self.assertEqual(self.art("4-G", 2027)["articulo"], "4-G")
        self.assertIsNone(self.art("4-G", 2026))

    def test_anio_por_defecto_no_adelanta_la_capa(self):
        from datetime import date
        self.assertEqual(store.anio_por_defecto("XLEY", hoy=date(2026, 12, 31), raiz=self.raiz), 2026)
        self.assertEqual(store.anio_por_defecto("XLEY", hoy=date(2027, 1, 1), raiz=self.raiz), 2027)
        # sin pedir año: el más reciente que no sea posterior al año en curso (hoy: 2026 o más, según el reloj; aquí solo se comprueba que coincida)
        self.assertEqual(self.art("3", None)["anio_vigencia"], store.anio_por_defecto("XLEY", raiz=self.raiz))

    def test_listar_leyes(self):
        filas = [(x["sigla"], x["anio_vigencia"], x["articulos"]) for x in store.listar_leyes(raiz=self.raiz)]
        self.assertEqual(filas, [("XLEY", 2026, 5), ("YLEY", 2026, 2), ("XLEY", 2027, 6), ("YLEY", 2027, 2)])

    def test_busqueda_sobre_la_vista(self):
        # "autorizadas" solo está en el art. 4 (derogado en 2027); "uno" en el 1 (heredado); "NUEVO" en el 3 de 2027
        r27 = store.buscar("tasa", ley="XLEY", anio=2027, raiz=self.raiz)
        self.assertEqual([(x["articulo"], x["anio_vigencia"]) for x in r27], [("3", 2027)])
        self.assertIn("35%", r27[0]["fragmento"])
        r26 = store.buscar("tasa", ley="XLEY", anio=2026, raiz=self.raiz)
        self.assertIn("30%", r26[0]["fragmento"])
        heredado = store.buscar("Régimen general", ley="XLEY", anio=2027, raiz=self.raiz)
        self.assertEqual([(x["articulo"], x["anio_vigencia"], x["ruta"]) for x in heredado], [("1", 2027, "leyes/2026/XLEY/art-0001.md")])
        self.assertEqual(store.buscar("deducciones autorizadas", ley="XLEY", anio=2027, raiz=self.raiz), [])  # el 4 ya está derogado ("Se deroga.")
        self.assertEqual(len(store.buscar("deducciones autorizadas", ley="XLEY", anio=2026, raiz=self.raiz)), 1)
        self.assertEqual(sorted(x["articulo"] for x in store.buscar("nuevo", ley="XLEY", anio=2027, raiz=self.raiz)), ["3", "4-G"])

    def test_temas_etiqueta_la_vista(self):
        docs = temas.documentos(self.raiz, 2027)
        self.assertEqual([(d["ley"], d["id"]) for d in docs if d["ley"] == "XLEY"], [("XLEY", i) for i in ("1", "2", "3", "4-F", "4-G")])  # sin el derogado
        arch = {d["id"]: d["archivo"] for d in docs if d["ley"] == "XLEY"}
        self.assertEqual(arch["1"], "leyes/2026/XLEY/art-0001.md")
        self.assertEqual(arch["3"], "leyes/2027/XLEY/art-0003.md")
        self.assertEqual(temas.fuentes(self.raiz, 2027)["XLEY"], A.SHA27)


class TestValidar(Base):
    def setUp(self):
        super().setUp()
        self.capa_x()

    def errores(self):
        return validar.validar_ley(self.ruta(2027), 2027, None, False)["errores"]

    def meta(self, **cambios):
        p = self.ruta(2027) / "_meta.json"
        m = json.loads(p.read_text(encoding="utf-8"))
        m.update(cambios)
        p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    def test_capa_valida(self):
        self.assertEqual(self.errores(), [])
        self.assertEqual(validar.validar_ley(self.ruta(2026), 2026, None, False)["errores"], [])

    def test_hereda_de_inexistente_o_no_anterior(self):
        self.meta(hereda_de=2025)
        self.assertTrue(any("hereda_de 2025 pero no existe" in e for e in self.errores()))
        self.meta(hereda_de=2027)
        self.assertTrue(any("no es anterior" in e for e in self.errores()))

    def test_vigente_desde(self):
        self.meta(vigente_desde="2027-02-30")
        self.assertTrue(any("fecha ISO válida" in e for e in self.errores()))
        self.meta(vigente_desde="2026-01-01")
        self.assertTrue(any("no es posterior" in e for e in self.errores()))

    def test_vigente_hasta_no_se_guarda(self):
        self.meta(vigente_hasta="2028-01-01")
        self.assertTrue(any("vigente_hasta" in e for e in self.errores()))

    def test_articulos_modificados_debe_coincidir(self):
        self.meta(articulos_modificados=["3", "4-G"])
        e = " | ".join(self.errores())
        self.assertIn("no coincide con los archivos", e)

    def test_articulo_identico_al_heredado(self):
        A.escribir_articulo(self.ruta(2027), "XLEY", 2027, "2", A.TEXTOS_BASE["2"], reforma="2026-12-31", sha=A.SHA27, descarga="2027-01-05")
        self.meta(articulos_modificados=["2", "3", "4", "4-G"])
        self.assertTrue(any("art. 2: idéntico al heredado" in e for e in self.errores()))

    def test_nuevo_que_choca_con_uno_heredado(self):
        self.meta(articulos_nuevos=["3", "4-G"])
        self.assertTrue(any("art. 3: se declara nuevo pero ya existe" in e for e in self.errores()))

    def test_articulo_nuevo_sin_declarar(self):
        self.meta(articulos_nuevos=[])
        self.assertTrue(any("art. 4-G: no existe en la capa heredada" in e for e in self.errores()))

    def test_conteo_sobre_la_vista(self):
        self.meta(articulos_extraidos=3)
        self.assertTrue(any("_meta dice 3 articulos, hay 6" in e for e in self.errores()))

    def test_hueco_en_la_vista(self):
        (self.ruta(2026) / "art-0002.md").unlink()
        self.assertTrue(any("huecos de numeracion" in e for e in self.errores()))

    def test_anio_del_archivo_de_la_capa(self):
        p = self.ruta(2027) / "art-0003.md"
        p.write_text(p.read_text(encoding="utf-8").replace("vigencia_anio: 2027", "vigencia_anio: 2026"), encoding="utf-8")
        self.assertTrue(any("vigencia_anio=2026 != carpeta 2027" in e for e in self.errores()))


class TestEmpaquetado(Base):
    def setUp(self):
        super().setUp()
        self.capa_x()
        self.capa_y()

    def contenido(self, salida):
        with tarfile.open(salida / "leyes-mx-datos.tar.gz") as t:
            return {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}

    def test_materializa_por_omision(self):
        m = empaquetar.construir(self.raiz, self.tmp / "o1", "2027.01.05", "2027-01-05")
        self.assertTrue(m["materializado"])
        self.assertEqual(m["esquema"], 1)  # los clientes anteriores lo siguen leyendo
        self.assertEqual(m["capas"], 2)
        c = self.contenido(self.tmp / "o1")
        nombres = sorted(n.split("/")[-1] for n in c if n.startswith("leyes/2027/XLEY/"))
        self.assertEqual(nombres, sorted(["_indice.md", "_meta.json", "art-0001.md", "art-0002.md", "art-0003.md", "art-0004.md", "art-0004-F.md", "art-0004-G.md", "transitorios.md"]))
        self.assertIn(b'vigencia_anio: 2027', c["leyes/2027/XLEY/art-0001.md"])
        self.assertIn(b'heredado_de_anio: 2026', c["leyes/2027/XLEY/art-0001.md"])
        self.assertIn(b'ultima_reforma_dof: "2026-12-31"', c["leyes/2027/XLEY/art-0001.md"])
        self.assertIn(b"vigencia_anio: 2027", c["leyes/2027/XLEY/transitorios.md"])  # los transitorios heredados también llevan el año de la vista
        self.assertNotIn(b"heredado_de_anio", c["leyes/2027/XLEY/art-0003.md"])  # lo que está en la capa va tal cual
        self.assertEqual(c["leyes/2027/XLEY/art-0003.md"], (self.ruta(2027) / "art-0003.md").read_bytes())
        meta = json.loads(c["leyes/2027/XLEY/_meta.json"])
        self.assertTrue(meta["materializada"])
        self.assertEqual(meta["articulos_extraidos"], 6)
        self.assertEqual(sorted(n.split("/")[-1] for n in c if n.startswith("leyes/2027/YLEY/")),
                         ["_indice.md", "_meta.json", "art-0001.md", "art-0002.md", "transitorios.md"])
        self.assertIn("leyes/2026/XLEY/art-0003.md", c)  # la base no se toca
        self.assertIn("INTEGRIDAD.json", c)

    def test_el_paquete_materializado_se_lee_igual_que_las_capas(self):
        empaquetar.construir(self.raiz, self.tmp / "o2", "2027.01.05", "2027-01-05")
        destino = self.tmp / "extraido"
        with tarfile.open(self.tmp / "o2" / "leyes-mx-datos.tar.gz") as t:
            t.extractall(destino)
        for id_ in ("1", "2", "3", "4", "4-F", "4-G"):
            a = store.obtener_articulo("XLEY", id_, anio=2027, raiz=self.raiz)
            b = store.obtener_articulo("XLEY", id_, anio=2027, raiz=destino)
            a.pop("ruta"), b.pop("ruta")
            self.assertEqual(a, b, id_)
        a = store.buscar("nuevo", ley="XLEY", anio=2027, raiz=self.raiz)
        b = store.buscar("nuevo", ley="XLEY", anio=2027, raiz=destino)
        self.assertEqual([(x["articulo"], x["fragmento"]) for x in a], [(x["articulo"], x["fragmento"]) for x in b])

    def test_sin_materializar_lleva_las_capas_y_sube_el_esquema(self):
        m = empaquetar.construir(self.raiz, self.tmp / "o3", "2027.01.05", "2027-01-05", materializar=False)
        self.assertFalse(m["materializado"])
        self.assertEqual(m["esquema"], 2)
        c = self.contenido(self.tmp / "o3")
        self.assertEqual(sorted(n.split("/")[-1] for n in c if n.startswith("leyes/2027/XLEY/")), sorted(["_indice.md", "_meta.json", "art-0003.md", "art-0004.md", "art-0004-G.md"]))

    def test_sin_capas_el_manifest_sigue_en_esquema_1(self):
        import shutil
        shutil.rmtree(self.ruta(2027))
        shutil.rmtree(self.ruta(2027, "YLEY"))
        m = empaquetar.construir(self.raiz, self.tmp / "o4", "2026.11.02", "2026-11-02", materializar=False)
        self.assertEqual((m["esquema"], m["capas"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
