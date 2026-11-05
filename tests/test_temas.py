import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import temas  # noqa: E402

VOC = {"temas": [
    {"id": "hidro", "nombre": "Hidrocarburos", "descripcion": "x", "palabras": ["hidrocarburo", "gas natural"], "citas": ["LISH"]},
    {"id": "firma", "nombre": "Firma", "descripcion": "x", "palabras": ["e.firma"], "umbral": 3},
]}


def doc(ley="X", id="1", enc="", texto="", citas=(), tipo="articulo"):
    return {"ley": ley, "id": id, "tipo": tipo, "archivo": f"x/{id}.md", "encabezado": enc, "texto": texto, "citas": list(citas)}


class TestNormalizar(unittest.TestCase):
    def test_acentos_mayusculas_y_signos(self):
        self.assertEqual(temas.normalizar("La e.Firma, Régimen: ÚNICO"), "la e firma regimen unico")


class TestVocabulario(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(temas.validar_vocabulario(VOC), [])

    def test_errores(self):
        malo = {"temas": [{"id": "Mal Id", "nombre": "", "descripcion": "x", "palabras": ["a", "A"]},
                          {"id": "ok", "nombre": "n", "descripcion": "d", "palabras": []}]}
        e = " | ".join(temas.validar_vocabulario(malo))
        self.assertIn("id inválido", e)
        self.assertIn("falta nombre", e)
        self.assertIn("palabras repetidas", e)
        self.assertIn("sin palabras ni citas", e)


class TestEtiquetar(unittest.TestCase):
    def ids(self, docs, tema):
        por, _ = temas.etiquetar(docs, VOC)
        return {(e[0], e[1]): e for e in por.get(tema, [])}

    def test_encabezado_basta_una_vez(self):
        r = self.ids([doc(enc="DEL IMPUESTO A LOS HIDROCARBUROS", texto="x" * 2000)], "hidro")
        self.assertEqual(r[("X", "1")][4], ["encabezado"])

    def test_umbral_en_texto_largo_y_corto(self):
        largo = "gas natural " + "y" * 2000
        self.assertEqual(self.ids([doc(texto=largo)], "hidro"), {})  # una vez en un texto largo: no basta (umbral 2)
        self.assertIn(("X", "1"), self.ids([doc(texto="gas natural y gas natural. " + "y" * 2000)], "hidro"))
        self.assertIn(("X", "1"), self.ids([doc(texto="El gas natural.")], "hidro"))  # texto corto: una vez basta

    def test_umbral_propio_del_tema(self):
        t = "e.firma " * 2 + "y" * 2000
        self.assertEqual(self.ids([doc(texto=t)], "firma"), {})
        self.assertIn(("X", "1"), self.ids([doc(texto="e.firma " * 3 + "y" * 2000)], "firma"))

    def test_plural_y_acentos(self):
        self.assertIn(("X", "1"), self.ids([doc(texto="Los hidrocarburos.")], "hidro"))

    def test_no_coincide_dentro_de_otra_palabra(self):
        self.assertEqual(self.ids([doc(texto="los hidrocarburosx")], "hidro"), {})

    def test_cita_de_una_ley(self):
        r = self.ids([doc(ley="RMF", id="10.1", tipo="regla", texto="nada", citas=["LISH", "CFF"])], "hidro")
        self.assertEqual(r[("RMF", "10.1")][4], ["fundamento"])

    def test_cobertura_cuenta_por_ley(self):
        _, cob = temas.etiquetar([doc(id="1", texto="El hidrocarburo."), doc(id="2", texto="otra cosa")], VOC)
        self.assertEqual(cob["X"], [2, 1])

    def test_es_determinista(self):
        docs = [doc(id=str(i), texto="hidrocarburo hidrocarburo") for i in (3, 1, 2)]
        a, _ = temas.etiquetar(docs, VOC)
        b, _ = temas.etiquetar(list(reversed(docs)), VOC)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
