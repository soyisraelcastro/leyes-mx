import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import glosario  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


class TestGlosario(unittest.TestCase):
    def test_el_glosario_del_repo_es_valido(self):
        errores, _ = glosario.validar(RAIZ)
        self.assertEqual(errores, [])

    def _con_glosario(self, modificar):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "leyes").symlink_to(RAIZ / "leyes")
        d = json.loads((RAIZ / "glosario.json").read_text(encoding="utf-8"))
        modificar(d)
        (tmp / "glosario.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return glosario.validar(tmp, anio=2026)[0]

    def test_evidencia_que_no_esta_en_el_articulo_se_rechaza(self):
        def mal(d):
            d["entradas"][0]["articulos"][0]["evidencia"] = "frase que la ley no dice"
        errores = self._con_glosario(mal)
        self.assertTrue(any("no aparece" in e for e in errores), errores)

    def test_articulo_inexistente_se_rechaza(self):
        def mal(d):
            d["entradas"][0]["articulos"][0]["articulo"] = "9999"
        self.assertTrue(any("no existe" in e for e in self._con_glosario(mal)))

    def test_sin_nota_o_con_raya_larga_se_rechaza(self):
        def sin_nota(d):
            d["entradas"][0]["nota"] = "corta"
        self.assertTrue(any("nota" in e for e in self._con_glosario(sin_nota)))

        def raya(d):
            d["entradas"][0]["nota"] = "Una nota larga — con raya larga que no se permite en el repo."
        self.assertTrue(any("raya larga" in e for e in self._con_glosario(raya)))

    def test_la_evidencia_ignora_acentos_y_mayusculas(self):
        def ok(d):
            d["entradas"][0]["articulos"][0]["evidencia"] = "NO SERA DEDUCIBLE NI ACREDITABLE"
        self.assertEqual(self._con_glosario(ok), [])


if __name__ == "__main__":
    unittest.main()
