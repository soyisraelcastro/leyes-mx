import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx.ids import normalizar_id, nombre_archivo, id_desde_archivo, clave_orden  # noqa: E402
from leyes_mx.extraer import encabezado_articulo  # noqa: E402


class TestIds(unittest.TestCase):
    def test_normalizar(self):
        casos = {"113 E": "113-E", "113-e": "113-E", "28": "28", "28 bis": "28-bis", "28-Bis": "28-bis",
                 "Artículo 1o.-A": "1-A", "32-B Bis": "32-B-bis", "18-H BIS": "18-H-bis", "353-ñ": "353-Ñ",
                 "82 Quáter": "82-quater", "113E": "113-E"}
        for entrada, esperado in casos.items():
            self.assertEqual(normalizar_id(entrada), esperado, entrada)
        self.assertIsNone(normalizar_id("abc"))

    def test_archivos(self):
        self.assertEqual(nombre_archivo("28"), "art-0028.md")
        self.assertEqual(nombre_archivo("113-E"), "art-0113-E.md")
        self.assertEqual(nombre_archivo("28-bis"), "art-0028-bis.md")
        self.assertEqual(nombre_archivo("32-B-bis"), "art-0032-B-bis.md")
        self.assertEqual(nombre_archivo("353-Ñ"), "art-0353-NN.md")
        for i in ["28", "113-E", "28-bis", "32-B-bis", "353-Ñ"]:
            self.assertEqual(id_desde_archivo(nombre_archivo(i)), i)

    def test_orden(self):
        ids = ["28-bis", "28", "28-A", "4-B", "4-A"]
        self.assertEqual(sorted(ids, key=clave_orden), ["4-A", "4-B", "28", "28-A", "28-bis"])

    def test_encabezados(self):
        ok = {"Artículo 1o.- Están": "1", "Artículo 1o.-A.- Están": "1-A", "Artículo 3o. Bis.- Para": "3-bis",
              "Artículo 22 Bis. Queda": "22-bis", "Artículo 113-E. Los": "113-E", "Artículo 890- Se deroga.": "890",
              "Artículo 2o.-C. (Se deroga).": "2-C", "Artículo 1o.-A BIS.- Los": "1-A-bis",
              # LSS: la letra va separada por espacio, sin guion
              "Artículo 15 A. La contratación": "15-A", "Artículo 5 A. Para los": "5-A", "Artículo 304 D. Los": "304-D"}
        for linea, esperado in ok.items():
            h = encabezado_articulo(linea)
            self.assertTrue(h, linea)
            self.assertEqual(h[0], esperado, linea)
        for linea in ["Artículo 123 Constitucional; de la Ley", "Artículo 28 de esta Ley establece", "Artículo adicionado DOF 09-12-2019",
                      "Artículo 10.- A los" if False else "Artículo reformado DOF 01-01-2020",
                      "Artículo 15 A de esta Ley", "Artículo 28 A partir de", "Artículo 5 Aquí se"]:
            self.assertIsNone(encabezado_articulo(linea), linea)


if __name__ == "__main__":
    unittest.main()
