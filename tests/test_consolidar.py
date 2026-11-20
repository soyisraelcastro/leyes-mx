"""Consolidación desde el DOF (leyes_mx/consolidar.py) sobre HTML sintético con la forma de dof.gob.mx."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import consolidar as C  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import revisar_reformas  # noqa: E402


def html(parrafos, salto_antes=()):
    """Cada página del DOF va envuelta en <div style= '' >; salto_antes: índices de párrafo que abren página."""
    out = ["<html><body><div style= '' >"]
    for i, p in enumerate(parrafos):
        if i in salto_antes:
            out.append("</div> <div style= '' >")
        out.append(f"<div style='x' class='Texto'> <span>{p}</span></div>")
    out.append("</div></body></html>")
    return "\n".join(out)


ORIGINAL = ["REGLAMENTO DE PRUEBA", "CAPÍTULO I", "Disposiciones Generales",
            "ARTÍCULO 1. Objeto del reglamento.", "ARTÍCULO 2. Los patrones están obligados a:",
            "I. Inscribirse;", "II. Pagar las aportaciones;", "III. Dar avisos.", "El aviso se da por escrito.",
            "ARTÍCULO 3. Texto viejo del tres.", "ARTÍCULO 4. Se paga el cinco por ciento", "del salario.",
            "TRANSITORIOS", "PRIMERO. Entra en vigor al día siguiente.", "Dado en la Residencia del Poder Ejecutivo Federal.- Rúbrica."]
DECRETO = ["DECRETO por el que se reforma el Reglamento de prueba.",
           "ARTÍCULO ÚNICO.- Se REFORMAN los artículos 2, fracción II; 3 y 4, párrafo segundo; se ADICIONA el artículo 5, para quedar como sigue:",
           "ARTÍCULO 2. ...", "I. ...", "II. Pagar las Aportaciones en medios electrónicos;", "III. ...", "...", "Las Aportaciones se pagan por mes.",
           "ARTÍCULO 3. Texto nuevo del tres.",
           "ARTÍCULO 4. ...", "Párrafo nuevo del cuatro.",
           "Capítulo II", "De los Medios Electrónicos", "ARTÍCULO 5. Artículo nuevo.",
           "TRANSITORIOS", "PRIMERO.- Entra en vigor al día siguiente.", "Dado en la Residencia del Poder Ejecutivo Federal.- Rúbrica."]
CFG = {"titulo": "REGLAMENTO DE PRUEBA", "nota_texto": "Prueba.",
       "original": {"url": "o", "fecha_dof": "2012-02-10"},
       "reformas": [{"url": "d", "fecha_dof": "2017-09-28", "fecha_texto": "28 de septiembre de 2017", "titulo": "por el que se reforma."}],
       "mapas": {"2017-09-28": {"2": [2, "+"], "4": ["+"]}}}


class TestConsolidar(unittest.TestCase):
    def test_parrafos_unen_salto_de_pagina(self):
        p = C.parrafos_dof(html(ORIGINAL, salto_antes={11}))
        self.assertIn("ARTÍCULO 4. Se paga el cinco por ciento del salario.", p)
        # sin salto de página no se une (un párrafo sin punto final es legítimo)
        self.assertIn("del salario.", C.parrafos_dof(html(ORIGINAL)))

    def test_consolida(self):
        fuentes = {"o": html(ORIGINAL, salto_antes={11}), "d": html(DECRETO)}
        texto, informe = C.texto_consolidado(CFG, fuentes)
        self.assertIn("II. Pagar las Aportaciones en medios electrónicos;", texto)
        self.assertNotIn("II. Pagar las aportaciones;", texto)
        self.assertIn("El aviso se da por escrito.", texto)          # el "..." lo conserva
        self.assertIn("Las Aportaciones se pagan por mes.", texto)   # adición
        self.assertIn("Texto nuevo del tres.", texto)
        self.assertNotIn("Texto viejo del tres.", texto)
        self.assertIn("ARTÍCULO 5. Artículo nuevo.", texto)
        self.assertLess(texto.index("Capítulo II"), texto.index("ARTÍCULO 5."))
        self.assertIn("Fracción reformada DOF 28-09-2017", texto)
        self.assertIn("Artículo adicionado DOF 28-09-2017", texto)
        self.assertIn("DECRETO por el que se reforma.\nPublicado en el Diario Oficial de la Federación el 28 de septiembre de 2017", texto)
        self.assertNotIn("Dado en la Residencia", texto)
        self.assertIn("ARTÍCULO 4. Se paga el cinco por ciento del salario.\n\nPárrafo nuevo del cuatro.", texto)
        self.assertTrue(any("art. 4" in x for x in informe))

    def test_mapa_mal_hecho_falla(self):
        fuentes = {"o": html(ORIGINAL), "d": html(DECRETO)}
        for mapa, msg in [({"2": [1, "+"], "4": ["+"]}, "inválido"),       # la unidad 1 ya la consumió el "I. ..."
                          ({"2": [3, "+"], "4": ["+"]}, "etiqueta"),       # la fracción II no puede sustituir a la III
                          ({"2": [2], "4": ["+"]}, "menos destinos"),
                          ({}, "no hay entrada en el mapa"),
                          ({"2": [2, "+"], "3": [0], "4": ["+"]}, "sustituye completo")]:
            cfg = dict(CFG, mapas={"2017-09-28": mapa})
            with self.assertRaisesRegex(ValueError, msg):
                C.texto_consolidado(cfg, fuentes)

    def test_adicion_al_final(self):
        dec = DECRETO[:6] + DECRETO[7:]  # sin el "..." que conserva el último párrafo del art. 2
        cfg = dict(CFG, mapas={"2017-09-28": {"2": [2, "+fin"], "4": ["+"]}})
        texto, _ = C.texto_consolidado(cfg, {"o": html(ORIGINAL), "d": html(dec)})
        self.assertLess(texto.index("El aviso se da por escrito."), texto.index("Las Aportaciones se pagan por mes."))

    def test_articulos_del_decreto(self):
        self.assertEqual(C.articulos_del_decreto(DECRETO[1]), {"2", "3", "4", "5"})
        unico = "Se REFORMAN los artículos 2; 30, fracción I, inciso a); 79, fracción II, inciso b) y 84, se ADICIONAN el 17-D del Código"
        self.assertEqual(C.articulos_del_decreto(unico), {"2", "30", "79", "84"})

    def test_decreto_que_no_cuadra_con_su_articulo_unico(self):
        dec = [x.replace("y 4, párrafo segundo", "") for x in DECRETO]
        with self.assertRaisesRegex(ValueError, "ARTÍCULO ÚNICO"):
            C.texto_consolidado(CFG, {"o": html(ORIGINAL), "d": html(dec)})

    def test_ficha_de_la_camara(self):
        pagina = ("<tr><td>REGLAMENTO de Otra Cosa</td><td>01/01/2001</td></tr>"
                  "<tr><td>REGLAMENTO de Inscripción, Pago de Aportaciones y Entero de\n Descuentos al Instituto</td>"
                  "<td>Reforma DOF 28/09/2017</td><td>10/02/2012</td></tr>")
        self.assertEqual(revisar_reformas.fechas_ficha_camara(pagina, "Inscripción, Pago de Aportaciones y Entero de Descuentos"),
                         ["2012-02-10", "2017-09-28"])
        self.assertIsNone(revisar_reformas.fechas_ficha_camara(pagina, "No existe"))


if __name__ == "__main__":
    unittest.main()
