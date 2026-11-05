import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import rmf  # noqa: E402


def linea(texto, left=234, top=100, b=False, i=False, p=1, w=300):
    return {"p": p, "top": top, "texto": texto, "chunks": [{"left": left, "w": w, "t": texto, "b": b, "i": i, "top": top}]}


class TestFundamento(unittest.TestCase):
    def test_leyes_y_reglas(self):
        leyes, reglas, parcial = rmf.parsear_fundamento("CFF 29, 29-A, 17-H Bis, RCFF 29, RMF 2.7.1.32., 2.7.2.14.")
        self.assertEqual(leyes, {"CFF": ["29", "29-A", "17-H-bis"], "RCFF": ["29"]})
        self.assertEqual(reglas, ["2.7.1.32", "2.7.2.14"])
        self.assertFalse(parcial)

    def test_texto_libre_marca_parcial(self):
        leyes, reglas, parcial = rmf.parsear_fundamento("CFF 69, Decretos región fronteriza norte 30/12/2020 Segundo, Sexto, RMF 11.9.1.")
        self.assertEqual(leyes["CFF"], ["69"])
        self.assertEqual(reglas, ["11.9.1"])
        self.assertTrue(parcial)

    def test_vacio(self):
        self.assertEqual(rmf.parsear_fundamento(""), ({}, [], False))


class TestLineas(unittest.TestCase):
    def test_id_solo_en_el_margen_y_en_negrita(self):
        self.assertEqual(rmf.id_regla(linea("2.7.1.1.", left=149, b=True)), "2.7.1.1")
        self.assertEqual(rmf.id_regla(linea("2.7.7.1.1.", left=149, b=True)), "2.7.7.1.1")  # cinco niveles (Subsección)
        self.assertEqual(rmf.id_regla(linea("2.4.17", left=149, b=True)), "2.4.17")  # el punto puede venir en otro fragmento
        # mención a otra regla dentro del texto: no abre regla
        self.assertIsNone(rmf.id_regla(linea("2.7.1.32.", left=234, b=False)))
        self.assertIsNone(rmf.id_regla(linea("2.7.1.32.", left=234, b=True)))

    def test_orden_y_nombre(self):
        self.assertLess(rmf.clave_regla("2.9.18"), rmf.clave_regla("2.10.1"))
        self.assertLess(rmf.clave_regla("3.9.18"), rmf.clave_regla("3.10.1"))
        self.assertEqual(rmf.nombre_archivo_regla("2.7.1.1"), "regla-2.7.1.1.md")
        self.assertLess(rmf.clave_regla("2.7.7.1.6"), rmf.clave_regla("2.7.7.2.1"))


class TestFormato(unittest.TestCase):
    def test_parrafos_por_espacio_vertical_y_fracciones(self):
        ls = [linea("Primer párrafo que sigue", top=100), linea("en otra línea.", top=117),
              linea("Segundo párrafo, tras un espacio mayor.", top=141),
              {"p": 1, "top": 165, "texto": "I. Fracción", "chunks": [
                  {"left": 234, "w": 20, "t": "I.", "b": False, "i": False, "top": 165},
                  {"left": 298, "w": 100, "t": "Fracción", "b": False, "i": False, "top": 165}]}]
        self.assertEqual(rmf.formatear(ls).split("\n\n"),
                         ["Primer párrafo que sigue en otra línea.", "Segundo párrafo, tras un espacio mayor.", "I. Fracción"])

    def test_texto_justificado_no_es_tabla(self):
        # un hueco de 40 px en una sola línea es justificación, no columnas
        ls = [{"p": 1, "top": 100, "texto": "a b", "chunks": [
            {"left": 234, "w": 100, "t": "de la", "b": False, "i": False, "top": 100},
            {"left": 374, "w": 100, "t": "AGGC, tratándose", "b": False, "i": False, "top": 100}]}]
        self.assertNotIn("```", rmf.formatear(ls))

    def test_columnas_anchas_si_son_tabla(self):
        fila = lambda top, a, b: {"p": 1, "top": top, "texto": a + " " + b, "chunks": [
            {"left": 234, "w": 50, "t": a, "b": False, "i": False, "top": top},
            {"left": 500, "w": 50, "t": b, "b": False, "i": False, "top": top}]}
        self.assertIn("```text", rmf.formatear([fila(100, "2", "0.9859"), fila(117, "3", "1.9581")]))


if __name__ == "__main__":
    unittest.main()
