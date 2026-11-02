import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import anexos, anexos_validar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PDF = RAIZ / "fuentes" / "2026" / anexos.NOMBRE_PDF

# Cifras clave copiadas del PDF del DOF 2025-12-28 (Anexo 8, apartados B.V y C.II).
MENSUAL_2026 = [
    ["0.01", "844.59", "0.00", "1.92"], ["844.60", "7,168.51", "16.22", "6.40"], ["7,168.52", "12,598.02", "420.95", "10.88"],
    ["12,598.03", "14,644.64", "1,011.68", "16.00"], ["14,644.65", "17,533.64", "1,339.14", "17.92"],
    ["17,533.65", "35,362.83", "1,856.84", "21.36"], ["35,362.84", "55,736.68", "5,665.16", "23.52"],
    ["55,736.69", "106,410.50", "10,457.09", "30.00"], ["106,410.51", "141,880.66", "25,659.23", "32.00"],
    ["141,880.67", "425,641.99", "37,009.69", "34.00"], ["425,642.00", "En adelante", "133,488.54", "35.00"],
]
ANUAL_2026 = [
    ["0.01", "10,135.11", "0", "1.92"], ["10,135.12", "86,022.11", "194.59", "6.40"], ["86,022.12", "151,176.19", "5,051.37", "10.88"],
    ["151,176.20", "175,735.66", "12,140.13", "16.00"], ["175,735.67", "210,403.69", "16,069.64", "17.92"],
    ["210,403.70", "424,353.97", "22,282.14", "21.36"], ["424,353.98", "668,840.14", "67,981.92", "23.52"],
    ["668,840.15", "1,276,925.98", "125,485.07", "30.00"], ["1,276,925.99", "1,702,567.97", "307,910.81", "32.00"],
    ["1,702,567.98", "5,107,703.92", "444,116.23", "34.00"], ["5,107,703.93", "En adelante", "1,601,862.46", "35.00"],
]


class TestAnexo8(unittest.TestCase):
    def test_cifras_clave(self):
        m = anexos.obtener_anexo(8, "B-V")
        self.assertEqual(m["filas"], MENSUAL_2026)
        self.assertEqual(m["publicado_dof"], "2025-12-28")
        self.assertEqual(m["vigencia_anio"], 2026)
        a = anexos.obtener_anexo(8, "C.II")
        self.assertEqual(a["filas"], ANUAL_2026)

    def test_31_tarifas_verificadas(self):
        tarifas = anexos.listar_anexo(8)
        self.assertEqual(len(tarifas), 31)
        for t in tarifas:
            f = anexos.obtener_anexo(8, t["id"])["filas"]
            self.assertEqual(anexos.verificar_tarifa(t["id"], f), [], t["id"])

    def test_error_de_parseo_rompe_la_verificacion(self):
        base = [list(f) for f in MENSUAL_2026]
        idm = "B-V-tarifa-mensual-2026"
        self.assertEqual(anexos.verificar_tarifa(idm, base), [])
        for fila, col, nuevo in [(2, 2, "421.95"), (3, 0, "12,598.04"), (4, 3, "17.82"), (5, 1, "17,533.65"), (6, 2, "5,665.19")]:
            mal = [list(f) for f in base]
            mal[fila][col] = nuevo
            self.assertTrue(anexos.verificar_tarifa(idm, mal), (fila, col, nuevo))
        self.assertTrue(anexos.verificar_tarifa(idm, base[:-1]))  # falta una fila

    def test_tolerancia_por_evidencia(self):
        self.assertEqual(anexos.tolerancia("B-V-tarifa-mensual-2026"), anexos.TOL_BASE)
        self.assertEqual(anexos.tolerancia("B-IV-15-dias"), anexos.TOL_BASE * 15)
        self.assertEqual(anexos.tolerancia("B-VI-noviembre"), anexos.TOL_BASE * 11)

    def test_limpiar_quita_encabezados_dof(self):
        t = "DIARIO OFICIAL                Domingo 28 de diciembre de 2025\nhola\f\nDomingo 28 de diciembre de 2025               DIARIO OFICIAL\nfin"
        self.assertEqual([l for l in anexos.limpiar(t) if l.strip()], ["hola", "fin"])

    def test_ambiguo_y_no_existe(self):
        self.assertIn("ambiguo", anexos.obtener_anexo(8, "B-VI"))
        self.assertIsNone(anexos.obtener_anexo(8, "Z-IX"))
        with self.assertRaises(ValueError):
            anexos.obtener_anexo(9, "B-V")

    def test_validador_detecta_un_digito_cambiado(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(RAIZ / "rmf", tmp / "rmf")
            e, _ = anexos_validar._validar_carpeta(tmp, 2026, False)
            self.assertEqual(e, [])
            p = tmp / "rmf" / "2026" / "anexo-8" / "B-V-tarifa-mensual-2026.md"
            p.write_text(p.read_text(encoding="utf-8").replace("| 844.60 | 7,168.51 | 16.22 |", "| 844.60 | 7,168.51 | 16.23 |"), encoding="utf-8")
            e, _ = anexos_validar._validar_carpeta(tmp, 2026, False)
            self.assertTrue(e)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(PDF.exists(), "sin el PDF local en fuentes/2026/ (ignorado por git)")
    def test_reextraccion_igual_a_lo_escrito(self):
        datos = anexos.extraer_pdf(PDF)
        self.assertEqual(len(datos["tablas"]), 31)
        self.assertEqual(anexos.contar_crudo(datos["lineas_cuerpo"], datos["tablas"]), [11] * 31)
        for t in datos["tablas"]:
            self.assertEqual(anexos.obtener_anexo(8, t["id"])["filas"], t["filas"], t["id"])


if __name__ == "__main__":
    unittest.main()
