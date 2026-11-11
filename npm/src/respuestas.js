// Redacción de las respuestas pensadas para un modelo de lenguaje y paginado de textos grandes.
import { AVISO_GENERAL, AVISO_PROYECTO, AVISO_RMF } from "./almacen.js";

/** Qué hacer cuando algo no está en la base. Va dentro del RESULTADO de las herramientas para que funcione en cualquier cliente. */
export const PERMISO_INTERNET = "Pregunta al usuario si desea que lo busques en internet; no busques sin su permiso. Si lo autoriza, usa solo fuentes oficiales " +
  "(DOF, SAT, Cámara de Diputados) y di claramente que ese dato no proviene de la base verificada de leyes-mx. No completes el texto, los porcentajes ni los montos de memoria.";

/** `que`: lo que no apareció, por ejemplo "LISR art. 9999". `detalle`: dato útil adicional (opcional). */
export function noEncontrado(que, detalle = "") {
  return `NO VERIFICADO: No encontré ${que} en la base local de leyes-mx.${detalle ? ` ${detalle}` : ""} ${PERMISO_INTERNET}`;
}

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
    return noEncontrado(`resultados para ${JSON.stringify(consulta)}`, "Antes de preguntar al usuario, prueba una vez más: si es un artículo conocido usa obtener_articulo; si no, reformula con los términos de la ley " +
      "(por ejemplo \"accesorios de las contribuciones\" en lugar de \"actualizaciones\") o acota con el parámetro ley.") + (amp.length ? "\n\n" + amp.join("\n") : "");
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
  if (!lista.length) return noEncontrado("el Anexo 8 de la RMF");
  const filas = lista.map((x) => `${String(x.apartado).padEnd(7)} ${String(x.id).padEnd(38)} ${x.titulo}`);
  return [`${lista[0].documento} | DOF ${lista[0].publicado_dof} | vigencia ${lista[0].anio_vigencia} | ${lista.length} tarifas`, "", ...filas,
    "", "Para una tarifa concreta usa obtener_tarifa con el id exacto (o el apartado cuando es único, p. ej. B-V mensual, C-II anual)."].join("\n");
}

const pesos = (x) => `$${Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Subsidio para el empleo: parámetros del decreto, UMA que publica el INEGI y, si se pidió, el texto de un documento. */
export function respuestaSubsidio(f) {
  const p = f.parametros, u = f.uma, d = f.calculo_derivado;
  const l = [
    `Subsidio para el empleo ${f.anio} | ${f.documento} | estatus: ${f.estatus} | datos descargados ${f.fecha_descarga}`,
    `Fundamento: ${f.fundamento}`, "",
    `Parámetros del decreto vigentes desde ${p.vigencia_desde} (verificados contra el texto publicado en el DOF; reforma del 31-12-2025, Artículo Segundo):`,
    `- Tope de ingresos mensuales: ${pesos(p.limite_ingresos_mensuales)} (sin contar primas de antigüedad, retiro, indemnizaciones ni otros pagos por separación).`,
    `- Subsidio mensual máximo: valor mensual de la UMA x ${p.porcentaje_uma_febrero_a_diciembre}%. En enero de ${f.anio}, x ${p.porcentaje_uma_enero}% (transitorio segundo; la UMA ${f.anio} entra en vigor el 1 de febrero).`,
    `- Pagos por periodos menores a un mes: (UMA mensual x porcentaje) / ${p.divisor_periodos_menores_a_un_mes} x días del periodo, sin exceder el máximo mensual. Pago único de varios meses: (UMA mensual x porcentaje) x número de meses.`,
    "- Se aplica contra el ISR a cargo del art. 96 de la LISR; si el impuesto es menor, la diferencia no se acredita después ni se entrega (Artículo Segundo, segundo párrafo, que la reforma no cambió).", "",
    "UMA que publica el INEGI en el DOF (el valor mensual lo usa el decreto):",
    ...Object.entries(u).map(([a, x]) => `- UMA ${a}: diario ${pesos(x.diario)}, mensual ${pesos(x.mensual)}, anual ${pesos(x.anual)}; vigente desde ${x.vigente_desde}. Fuente: ${x.fuente_url}`), "",
    `${d.aviso}`,
    `- Enero ${f.anio}: UMA mensual ${pesos(d.enero_2026.uma_mensual)} x ${d.enero_2026.porcentaje}% = ${pesos(d.enero_2026.subsidio_mensual_maximo)}`,
    `- Febrero a diciembre ${f.anio}: UMA mensual ${pesos(d.febrero_a_diciembre_2026.uma_mensual)} x ${d.febrero_a_diciembre_2026.porcentaje}% = ${pesos(d.febrero_a_diciembre_2026.subsidio_mensual_maximo)}`, "",
    ...f.no_verificado.map((x) => `NO VERIFICADO: ${x}`), "",
    "Documentos (texto íntegro con obtener_subsidio_empleo(documento=\"<id>\")):",
    ...f.documentos.map((x) => `- ${x.id} | ${x.tipo}${x.publicado_dof ? ` | DOF ${x.publicado_dof}` : ""} | ${x.estatus}`), "", f.aviso,
  ];
  const t = f.texto_documento;
  if (t) {
    l.push("", `=== ${t.titulo} (${t.id}${t.publicado_dof ? `, DOF ${t.publicado_dof}` : ""}; estatus: ${t.estatus}) ===`);
    if (t.fuente_url) l.push(`Fuente: ${t.fuente_url}`);
    if (t.aviso) l.push(`AVISO: ${t.aviso}`);
    l.push("", t.texto);
  }
  return l.join("\n");
}

export function respuestaRegla(f, pagina = 1) {
  const cab = [`${f.nombre_ley || f.ley} (${f.ley}), regla ${f.regla}`, `Título de la regla: ${f.titulo}`,
    `Cita: ${f.ley} regla ${f.regla}, vigencia ${f.anio_vigencia}, publicada en el DOF ${f.publicacion_dof}`,
    `Ubicación: ${f.ubicacion}`, `Estatus: ${f.estatus}`, `Fuente: ${f.fuente_url} (descargado ${f.fecha_descarga}; página ${f.pagina_pdf} del PDF)`];
  if (f.estatus === "derogado") cab.push("AVISO: esta regla está derogada; no aplica salvo disposición transitoria.");
  cab.push(f.modificaciones_aplicadas?.length ? `Modificaciones aplicadas: ${f.modificaciones_aplicadas.join("; ")}.` : `AVISO: ${AVISO_RMF}`);
  const cola = [];
  if (f.fundamento) cola.push(`Fundamento (tal como lo imprime la RMF): ${f.fundamento}`);
  const refs = Object.entries(f.referencias_leyes || {}).map(([l, a]) => `${l} ${a.join(", ")}`);
  if (refs.length || f.referencias_reglas?.length) {
    cola.push(`Remite a: ${[...refs, ...(f.referencias_reglas?.length ? [`RMF ${f.referencias_reglas.join(", ")}`] : [])].join("; ")}. ` +
      "Léelo con obtener_articulo (leyes) u obtener_regla (reglas) antes de afirmar algo apoyado en esas remisiones.");
  }
  return conPaginas(cab.join("\n"), f.texto, pagina, `obtener_regla(regla="${f.regla}"`, cola.join("\n"));
}

export function respuestaTemas(info) {
  const filas = [...info.temas].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")).map((t) => `${t.id} | ${t.nombre} | ${t.documentos} documentos | ${t.descripcion}`);
  return [`${info.temas.length} temas (vigencia ${info.anio}) sobre ${info.documentos} documentos entre artículos de ley y reglas de la RMF.`, "",
    "id | nombre | documentos | qué cubre", ...filas, "",
    "Para ver los documentos de un tema: temas(tema=\"<id o nombre>\"). Los temas se asignan por palabras de la ley (ver docs/temas.md): " +
    "un documento \"menciona o trata\" el tema; el puntaje ordena de lo más central a lo más tangencial.", AVISO_GENERAL].join("\n");
}

export function respuestaTema(tema, r, { ley = null, minimo = 1 } = {}) {
  const filtro = [ley ? `ley ${String(ley).toUpperCase()}` : null, minimo > 1 ? `puntaje >= ${minimo}` : null].filter(Boolean).join(", ");
  const l = [`Tema: ${tema.nombre} (${tema.id}), vigencia ${r.anio}`, tema.descripcion,
    `Palabras con las que se asigna: ${tema.palabras.join(", ") || "(solo por citas en el fundamento de las reglas)"}.`,
    `${r.total} documentos${filtro ? ` (${filtro})` : ""}; se muestran ${r.lista.length}, de mayor a menor puntaje. ` +
    "Puntaje: 5 por coincidencia en el encabezado, 1 por cada una en el texto (máx. 20) y 3 por citar la ley; \"donde\" dice de dónde viene.", ""];
  r.lista.forEach((x, i) => {
    const que = x.tipo === "regla" ? `RMF regla ${x.id}` : `${x.ley} art. ${x.id}`;
    l.push(`${i + 1}. ${que} | puntaje ${x.puntaje} (${x.donde.join(", ")}) | ${x.titulo ?? ""}`);
  });
  if (r.total > r.lista.length) l.push("", `Hay ${r.total - r.lista.length} más: sube limite, filtra con ley, o sube minimo para quedarte con lo más central.`);
  l.push("", "Esto es un índice, no el texto: para citar, lee cada artículo con obtener_articulo y cada regla con obtener_regla.", AVISO_GENERAL);
  return l.join("\n");
}
