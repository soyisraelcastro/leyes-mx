// Redacción de las respuestas pensadas para un modelo de lenguaje y paginado de textos grandes.
import { AVISO_GENERAL, AVISO_PROYECTO } from "./almacen.js";

export const TAM_PAGINA = 40000; // caracteres por respuesta; por debajo de los límites de salida habituales de los clientes MCP

/** Parte el texto en páginas de hasta `tam` caracteres, cortando en saltos de párrafo (o duro si un párrafo es enorme). */
export function paginar(texto, tam = TAM_PAGINA) {
  if (texto.length <= tam) return [texto];
  const paginas = [];
  let actual = "";
  const pushDuro = (p) => { for (let i = 0; i < p.length; i += tam) paginas.push(p.slice(i, i + tam)); };
  for (const p of texto.split("\n\n")) {
    const con = actual ? actual + "\n\n" + p : p;
    if (con.length <= tam) { actual = con; continue; }
    if (actual) { paginas.push(actual); actual = ""; }
    if (p.length > tam) pushDuro(p); else actual = p;
  }
  if (actual) paginas.push(actual);
  return paginas;
}

export function citaArticulo(f) {
  return `${f.ley} art. ${f.articulo}, vigencia ${f.anio_vigencia}, última reforma DOF ${f.ultima_reforma_dof ?? "sin dato"}`;
}

function encabezado(f, titulo) {
  const l = [titulo];
  l.push(`Vigencia: ${f.anio_vigencia} | Última reforma DOF: ${f.ultima_reforma_dof ?? "no aplica (proyecto)"} | Estatus: ${f.estatus}`);
  if (f.fuente_url) l.push(`Fuente: ${f.fuente_url} (descargado ${f.fecha_descarga})`);
  if (f.aviso) l.push(`AVISO: ${f.aviso}${f.entrada_en_vigor ? ` Entraría en vigor: ${f.entrada_en_vigor}.` : ""}`);
  if (f.estatus === "derogado") l.push("AVISO: este artículo está derogado; no aplica salvo disposición transitoria.");
  for (const a of f.advertencias || []) l.push(`ADVERTENCIA: ${a}`);
  return l.join("\n");
}

function conPaginas(cabecera, texto, pagina, comando, cola) {
  const pags = paginar(texto);
  const total = pags.length;
  if (pagina < 1 || pagina > total) {
    return { texto: `Página ${pagina} fuera de rango: el texto tiene ${total} página(s).`, total, pagina, error: true };
  }
  const partes = [cabecera];
  if (total > 1) {
    partes.push(`TEXTO EXTENSO (${texto.length} caracteres): se entrega por páginas de hasta ${TAM_PAGINA} caracteres. Esta es la página ${pagina} de ${total}.` +
      (pagina < total ? ` Pide la siguiente con ${comando}, pagina=${pagina + 1}.` : " Es la última página."));
  }
  partes.push("", pags[pagina - 1]);
  if (cola && pagina === total) partes.push("", cola);
  partes.push("", AVISO_GENERAL);
  return { texto: partes.join("\n"), total, pagina };
}

export function respuestaArticulo(f, pagina = 1) {
  const cab = encabezado(f, `${f.nombre_ley || f.ley} (${f.ley}), artículo ${f.articulo}\nCita: ${citaArticulo(f)}`);
  const notas = f.notas_reforma?.length ? "Notas de reforma:\n" + f.notas_reforma.map((n) => `- ${n}`).join("\n") : "";
  return conPaginas(cab, f.texto, pagina, `obtener_articulo(ley="${f.ley}", articulo="${f.articulo}"`, notas);
}

export function respuestaTransitorios(t, pagina = 1) {
  const cab = encabezado({ ...t, articulo: "transitorios" }, `Transitorios de ${t.nombre_ley || t.ley} (${t.ley})`);
  return conPaginas(cab, t.texto, pagina, `obtener_transitorios(ley="${t.ley}"`, "");
}

/** Líneas que declaran, sin esconder nada, cómo el glosario cambió la consulta. Vacío si no hubo ampliación. */
export function lineasAmpliacion(amp) {
  if (!amp?.entradas?.length) return [];
  const l = [];
  const ids = (xs) => xs.map((e) => e.id).join(", ");
  if (amp.agregados.length) l.push(`Se amplió la consulta con: ${amp.agregados.join("; ")} (glosario: ${ids(amp.entradas.filter((e) => e.agregados.length))}).`);
  const sust = amp.entradas.filter((e) => e.sustituye.length);
  if (sust.length) l.push(`Se sustituyó ${[...new Set(sust.flatMap((e) => e.sustituye))].map((t) => JSON.stringify(t)).join(", ")} por su nombre en la ley (glosario: ${ids(sust)}).`);
  const rel = [...new Set(amp.entradas.filter((e) => e.relacionar).flatMap((e) => e.articulos.map((a) => `${a.ley} ${a.articulo}`)))];
  if (rel.length) l.push(`Artículos que el glosario relaciona con el tema (marcados [glosario]): ${rel.join(", ")}.`);
  for (const e of amp.entradas) l.push(`Nota del glosario (${e.id}): ${e.nota}`);
  l.push("Para buscar solo con tus palabras: glosario=false (CLI: --sin-glosario).");
  return l;
}

export function respuestaBusqueda(consulta, res, { incluirProyectos, anio, ampliacion = null } = {}) {
  const amp = lineasAmpliacion(ampliacion);
  if (!res.length) {
    return `Sin resultados para ${JSON.stringify(consulta)}. NO VERIFICADO: no se encontró en la base local; no se completa de memoria. ` +
      "Si es un artículo conocido usa obtener_articulo; si no, reformula con los términos de la ley (por ejemplo \"accesorios de las contribuciones\" en lugar de \"actualizaciones\"); " +
      "si tampoco aparece, consulta la fuente oficial (DOF, diputados.gob.mx)." + (amp.length ? "\n\n" + amp.join("\n") : "");
  }
  const l = [`${res.length} resultado(s) para ${JSON.stringify(consulta)} (búsqueda por palabras clave, ordenados por relevancia)${incluirProyectos ? "; incluye proyectos" : "; solo ley vigente"}:`];
  if (amp.length) l.push("", ...amp);
  l.push("");
  res.forEach((r, i) => {
    const marca = r.estatus === "proyecto" || (r.estatus !== "vigente" && r.estatus !== "derogado") ? " [PROYECTO, NO ES LEY VIGENTE]" : r.estatus === "derogado" ? " [derogado]" : "";
    l.push(`${i + 1}. ${r.ley} art. ${r.articulo} | vigencia ${r.anio_vigencia} | última reforma DOF ${r.ultima_reforma_dof ?? "sin dato"}${marca}${r.relacionado_por_glosario ? " [glosario]" : ""}`);
    l.push(`   ${r.fragmento}`);
  });
  l.push("", "Son fragmentos. Para citar, pide el artículo completo con obtener_articulo.", AVISO_GENERAL);
  return l.join("\n");
}

export function respuestaLeyes(leyes, version) {
  const l = ["Ordenamientos disponibles en la base local" + (version ? ` (datos ${version})` : "") + ":", ""];
  for (const x of leyes) {
    l.push(`${x.sigla} | ${x.nombre ?? "(proyecto)"} | vigencia ${x.anio_vigencia} | ${x.estatus} | ${x.articulos} artículos | última reforma DOF ${x.ultima_reforma_dof ?? "sin dato"}`);
  }
  l.push("", "Lo que no aparece aquí no está en la base: no se cita de memoria.", AVISO_GENERAL);
  return l.join("\n");
}

export function respuestaEstado(e, leyes, version) {
  const l = [];
  if (!e.disponible) l.push(`Sin seguimiento de reforma para el año ${e.anio ?? "solicitado"}.`);
  else {
    l.push(`ESTADO DE LA REFORMA ${e.anio} (actualizado ${e.actualizado})`, `es_ley_vigente: ${e.es_ley_vigente}`, "", AVISO_PROYECTO, "", e.resumen || "");
    if (e.entrada_en_vigor_prevista) l.push("", `Entrada en vigor prevista: ${e.entrada_en_vigor_prevista}`);
    if (e.hitos?.length) {
      l.push("", "Línea de tiempo (nivel: oficial, prensa o pendiente; confirmado sí/no):");
      for (const h of e.hitos) l.push(`- ${h.fecha ?? "s/f"} ${h.hito} [${h.nivel}, ${h.confirmado ? "confirmado" : "no confirmado"}] ${h.detalle ?? ""}${h.fuente ? ` Fuente: ${h.fuente}` : ""}`);
    }
  }
  l.push("", `Última reforma DOF por ley en la base${version ? ` (datos ${version})` : ""}:`);
  for (const x of leyes) l.push(`- ${x.sigla} ${x.anio_vigencia}: ${x.ultima_reforma_dof ?? "sin dato"}`);
  l.push("", AVISO_GENERAL);
  return l.join("\n");
}

export function respuestaTarifa(t) {
  return [
    `${t.documento}, apartado ${t.apartado} | vigencia ${t.vigencia_anio} | publicado en el DOF ${t.publicado_dof} (firma ${t.fecha_firma}) | estatus: ${t.estatus}`,
    `Aplicable a: ${(t.aplicable_a || []).join("; ")}`,
    `fuente: ${t.fuente_url}`,
    "",
    t.texto,
  ].join("\n");
}

export function respuestaTarifas(lista) {
  if (!lista.length) return "NO VERIFICADO: no hay Anexo 8 de la RMF en la base local.";
  const filas = lista.map((x) => `${String(x.apartado).padEnd(7)} ${String(x.id).padEnd(38)} ${x.titulo}`);
  return [`${lista[0].documento} | DOF ${lista[0].publicado_dof} | vigencia ${lista[0].anio_vigencia} | ${lista.length} tarifas`, "", ...filas,
    "", "Para una tarifa concreta usa obtener_tarifa con el id exacto (o el apartado cuando es único, p. ej. B-V mensual, C-II anual)."].join("\n");
}
