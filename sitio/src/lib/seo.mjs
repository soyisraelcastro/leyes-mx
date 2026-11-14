// Datos estructurados (JSON-LD) y textos para LLMs. Una sola fuente para Base.astro, /llms.txt y /llms-full.txt.
// Las cifras se leen de los datos del repo en el build; aquí solo vive el copy que describe el proyecto.
import { leyes, reforma, anexo8 } from "./datos.mjs";
import { REPO, TODOCONTA, ABACUS, COMANDO } from "./constantes.mjs";
import { RUTAS } from "./docs.mjs";

export const NOMBRES = {
  LISR: "Ley del Impuesto sobre la Renta", RLISR: "Reglamento de la Ley del Impuesto sobre la Renta",
  LIVA: "Ley del Impuesto al Valor Agregado", RLIVA: "Reglamento de la Ley del Impuesto al Valor Agregado",
  CFF: "Código Fiscal de la Federación", RCFF: "Reglamento del Código Fiscal de la Federación", LFT: "Ley Federal del Trabajo",
  LSS: "Ley del Seguro Social", RACERF: "Reglamento de la Ley del Seguro Social en Materia de Afiliación, Clasificación de Empresas, Recaudación y Fiscalización",
  LFDC: "Ley Federal de los Derechos del Contribuyente", LCF: "Ley de Coordinación Fiscal", LIEPS: "Ley del Impuesto Especial sobre Producción y Servicios",
  LIF: "Ley de Ingresos de la Federación para el Ejercicio Fiscal de 2026",
  LOPDC: "Ley Orgánica de la Procuraduría de la Defensa del Contribuyente",
};
const ORDEN = ["LISR", "RLISR", "LIVA", "RLIVA", "CFF", "RCFF", "LFDC", "LOPDC", "LCF", "LIEPS", "LIF", "LFT", "LSS", "RACERF"];

export const RESUMEN = "leyes-mx es una base gratuita y de código abierto con el texto de las leyes fiscales y laborales de México "
  + "(LISR, LIVA, CFF, LFT, LSS, LFDC, LCF, LOPDC, LIEPS, LIF y sus reglamentos, más las tarifas de ISR del Anexo 8 de la RMF) para que los asistentes de IA "
  + "(Claude Desktop, Claude Code, Codex, Cursor y otros clientes MCP) citen ley, artículo, fracción, año de vigencia y fecha "
  + "de la última reforma en el DOF, en lugar de inventarlos. Se instala con un comando y consulta el texto guardado en la computadora.";

/** Cifras del build, compartidas por todas las salidas. */
export function cifras() {
  const lista = leyes();
  const orden = [...lista].sort((a, b) => ORDEN.indexOf(a.sigla) - ORDEN.indexOf(b.sigla));
  return {
    lista: orden,
    total: lista.reduce((n, l) => n + l.articulos, 0),
    anios: [...new Set(lista.map((l) => l.anio))].sort(),
    anexo: anexo8(),
    ref: reforma(),
  };
}

const abs = (site, ruta) => new URL(ruta, site).toString();

/** Nodos que van en todas las páginas: la organización y el sitio. */
export function grafoBase(site) {
  return [
    { "@type": "Organization", "@id": `${TODOCONTA}/#organization`, name: "TodoConta", url: TODOCONTA,
      logo: abs(site, "/favicon.svg"), sameAs: [REPO] },
    { "@type": "WebSite", "@id": abs(site, "/#website"), url: abs(site, "/"), name: "leyes-mx", inLanguage: "es-MX",
      description: RESUMEN, publisher: { "@id": `${TODOCONTA}/#organization` } },
  ];
}

/** Portada: el software (lo que se instala) y el conjunto de datos (los textos legales). */
export function grafoPortada(site) {
  const { lista, total, anios, anexo } = cifras();
  const fuente = { "@id": `${TODOCONTA}/#organization` };
  return [
    { "@type": "SoftwareApplication", "@id": abs(site, "/#software"), name: "leyes-mx", url: abs(site, "/"),
      applicationCategory: "BusinessApplication", applicationSubCategory: "Servidor MCP y CLI de consulta legal",
      operatingSystem: "Windows, macOS, Linux (Node.js 20 o superior)", inLanguage: "es-MX",
      description: RESUMEN, installUrl: abs(site, "/docs/instalar"), downloadUrl: "https://www.npmjs.com/package/leyes-mx",
      softwareHelp: abs(site, "/docs"), codeRepository: REPO, license: "https://opensource.org/licenses/MIT",
      offers: { "@type": "Offer", price: "0", priceCurrency: "MXN" }, publisher: fuente, image: abs(site, "/og.png") },
    { "@type": "Dataset", "@id": abs(site, "/#dataset"),
      name: `Leyes fiscales y laborales de México en Markdown, vigencia ${anios.join(", ")}`,
      description: `Texto de ${lista.map((l) => l.sigla).join(", ")} (${total.toLocaleString("es-MX")} artículos, un archivo por artículo) `
        + `copiado de la Cámara de Diputados, con año de vigencia, fecha de última reforma en el DOF y sha256 de la fuente`
        + (anexo ? `, más las ${anexo.tarifas} tarifas de ISR del Anexo 8 de la RMF ${anexo.anio}` : "")
        + `. Los proyectos de reforma van aparte y nunca como ley vigente.`,
      url: abs(site, "/docs/leyes"), sameAs: REPO, inLanguage: "es-MX", isAccessibleForFree: true,
      license: "https://opensource.org/licenses/MIT", creator: fuente, publisher: fuente,
      spatialCoverage: { "@type": "Country", name: "México" }, temporalCoverage: anios.join("/"),
      keywords: ["leyes de México", "LISR", "LIVA", "CFF", "LFT", "LSS", "IMSS", "LFDC", "LCF", "PRODECON", "ISR", "IVA", "Código Fiscal", "Ley Federal del Trabajo", "DOF", "Anexo 8 RMF", "MCP", "asistente de IA", "contadores", "abogados"],
      isBasedOn: lista.map((l) => `https://www.diputados.gob.mx/LeyesBiblio/pdf/${l.sigla}.pdf`),
      distribution: [{ "@type": "DataDownload", encodingFormat: "text/markdown", contentUrl: `${REPO}/releases` }] },
  ];
}

/** Migas de pan para las páginas de documentación. */
export function grafoMigas(site, nombre, ruta) {
  return [{ "@type": "BreadcrumbList", itemListElement: [
    { "@type": "ListItem", position: 1, name: "leyes-mx", item: abs(site, "/") },
    { "@type": "ListItem", position: 2, name: "Documentación", item: abs(site, "/docs") },
    ...(ruta === "/docs" ? [] : [{ "@type": "ListItem", position: 3, name: nombre, item: abs(site, ruta) }]),
  ] }];
}

export const PAGINAS = [
  { ruta: "/", titulo: "Inicio", que: "qué es leyes-mx, cómo responde un asistente con la base instalada y qué leyes incluye" },
  { ruta: "/docs", titulo: "Documentación", que: "índice de la documentación" },
  ...RUTAS.map((r) => ({ ruta: r.href, titulo: r.nombre, que: {
    "/docs/instalar": `cómo instalarlo con "${COMANDO}" en Claude Desktop (modo Code), Claude Code, Codex, Cursor o la Terminal`,
    "/docs/verificar": "cómo comprobar que el asistente ya usa leyes-mx",
    "/docs/actualizar": "cómo traer una reforma nueva y cómo volver a la versión anterior",
    "/docs/leyes": "lista de ordenamientos con año de vigencia, número de artículos y fecha de última reforma en el DOF",
    "/docs/tarifas": "tarifas de ISR de los artículos 96 y 152 de la LISR y del Anexo 8 de la RMF",
    "/docs/subsidio-empleo": "subsidio para el empleo 2026: decretos del DOF, tope de ingresos, porcentaje de la UMA y valores de la UMA",
    "/docs/reforma-2027": "estado de la reforma fiscal 2027 (publicada en el DOF, no vigente antes de su entrada en vigor) y sus fechas",
    "/docs/aviso": "fuente de los textos y límites de uso",
    "/docs/contribuir": "repositorio, origen de los datos y reglas para programadores",
  }[r.href] ?? r.nombre })),
  { ruta: "/contribuir", titulo: "Contribuir", que: "cómo reportar un error, proponer un sinónimo contable o pedir una ley, sin programar" },
];

export const HERRAMIENTAS = [
  ["buscar", "busca por tema en las leyes (con glosario de sinónimos contables) y devuelve fragmentos"],
  ["obtener_articulo", "texto íntegro de un artículo con vigencia, fecha de última reforma y advertencias"],
  ["obtener_tarifa", "tarifas de ISR del Anexo 8 de la RMF (mensual, anual, por periodos)"],
  ["obtener_subsidio_empleo", "decretos del subsidio para el empleo (DOF), el tope y el porcentaje de la UMA de 2026 y la UMA vigente"],
  ["estado_reforma", "estado de un proyecto de reforma; nunca lo presenta como ley vigente"],
  ["listar_leyes", "ordenamientos y años disponibles"],
  ["obtener_transitorios", "artículos transitorios de una ley"],
];

export const ENLACES = { REPO, TODOCONTA, ABACUS, COMANDO };

/** Nombre legible de cada hito de proyectos/<año>/estado.json. */
export const HITOS = {
  iniciativa: "Iniciativa del Ejecutivo federal",
  dictamen_comision_camara: "Dictamen de la Comisión de Hacienda de la Cámara de Diputados",
  aprobado_camara: "Aprobada por el pleno de la Cámara de Diputados",
  aprobado_senado_con_modificaciones: "Aprobada por el Senado con modificaciones",
  senado_lif_lfd: "Ley de Ingresos y Ley Federal de Derechos aprobadas por el Senado",
  camara_vota_cambios_senado: "La Cámara vota los cambios del Senado",
  publicado_dof: "Publicación en el DOF",
  verificacion_otros_decretos_dof: "Otros decretos del paquete (Ley Aduanera, Economía Digital, Catastral y Registral, Presupuesto): no verificado",
};
