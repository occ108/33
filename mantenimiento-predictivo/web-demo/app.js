export const MAX_BYTES = 10 * 1024 * 1024;
export const MAX_ROWS = 100_000;
export const SENSOR_INFO = {
  temperature_c: { label: 'Temperatura', unit: '°C' },
  vibration_mm_s: { label: 'Vibración', unit: 'mm/s RMS' },
  pressure_bar: { label: 'Presión', unit: 'bar' },
};
export const DEMO_CSV = `timestamp,asset_id,temperature_c,vibration_mm_s,pressure_bar,operating_hours
2026-01-01T08:00:00Z,BOMBA-001,52.0,1.8,4.1,1000
2026-01-01T09:00:00Z,BOMBA-001,52.5,1.9,4.0,1001
2026-01-01T10:00:00Z,BOMBA-001,53.0,2.0,4.1,1002
2026-01-01T11:00:00Z,BOMBA-001,55.0,2.2,4.0,1003
2026-01-01T12:00:00Z,BOMBA-001,57.0,2.5,3.9,1004
2026-01-01T13:00:00Z,BOMBA-001,58.0,2.7,3.9,1005
2026-01-01T08:00:00Z,BOMBA-002,48.0,1.4,4.2,800
2026-01-01T09:00:00Z,BOMBA-002,48.5,1.5,4.2,801
2026-01-01T10:00:00Z,BOMBA-002,48.3,1.4,4.1,802
`;

export function parseCSV(text) {
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  text = text.replace(/^\uFEFF/, '');
  const finishField = () => { row.push(field); field = ''; closed = false; };
  const finishRow = () => { finishField(); if (row.length > 1 || row[0] !== '') rows.push(row); row = []; if (rows.length > MAX_ROWS + 1) throw new Error('El archivo supera el límite de 100.000 lecturas.'); };
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') { field += '"'; index++; }
        else { quoted = false; closed = true; }
      } else field += char;
    } else if (char === ',') finishField();
    else if (char === '\n' || char === '\r') { if (char === '\r' && text[index + 1] === '\n') index++; finishRow(); }
    else if (char === '"') { if (field || closed) throw new Error('Hay comillas incorrectas en el CSV.'); quoted = true; }
    else { if (closed) throw new Error('Hay caracteres después de una comilla de cierre.'); field += char; }
  }
  if (quoted) throw new Error('El CSV contiene un campo con comillas sin cerrar.');
  if (field || row.length || closed) finishRow();
  return rows;
}

function parseTimestamp(value) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?(Z|[+-]\d{2}:\d{2})?)?$/);
  if (!match) throw new Error('Hay fechas inválidas; utiliza ISO 8601, por ejemplo 2026-01-01T08:00:00Z.');
  const [, year, month, day, hour, minute, second, fraction, zone] = match;
  const daysInMonth = new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate();
  if (+month < 1 || +month > 12 || +day < 1 || +day > daysInMonth || +(hour || 0) > 23 || +(minute || 0) > 59 || +(second || 0) > 59 || (zone && zone !== 'Z' && (+zone.slice(1, 3) > 23 || +zone.slice(4) > 59))) throw new Error('Hay una fecha u hora fuera de rango.');
  const normalized = `${year}-${month}-${day}T${hour || '00'}:${minute || '00'}:${second || '00'}.${(fraction || '').padEnd(3, '0').slice(0, 3)}${zone || 'Z'}`;
  const millis = Date.parse(normalized);
  if (!Number.isFinite(millis)) throw new Error('Hay una fecha fuera del rango admitido.');
  const nanos = BigInt(millis) * 1_000_000n + BigInt((fraction || '').padEnd(9, '0').slice(3) || '0');
  return { millis, key: nanos.toString(), iso: new Date(millis).toISOString() };
}

export function validateCSV(text) {
  if (new TextEncoder().encode(text).byteLength > MAX_BYTES) throw new Error('El archivo supera el límite de 10 MiB.');
  const parsed = parseCSV(text);
  if (parsed.length < 2) throw new Error('El CSV debe incluir una cabecera y al menos una lectura.');
  const headers = parsed.shift();
  if (new Set(headers).size !== headers.length) throw new Error('Hay nombres de columnas duplicados.');
  const missing = ['timestamp', 'asset_id'].filter(name => !headers.includes(name));
  if (missing.length) throw new Error(`Faltan columnas obligatorias: ${missing.join(', ')}. Usa comas como separador.`);
  const sensors = Object.keys(SENSOR_INFO).filter(name => headers.includes(name));
  if (!sensors.length) throw new Error('Incluye al menos un sensor: temperature_c, vibration_mm_s o pressure_bar.');
  if (parsed.length > MAX_ROWS) throw new Error('El archivo supera el límite de 100.000 lecturas.');
  const numeric = [...sensors, ...(headers.includes('operating_hours') ? ['operating_hours'] : [])];
  const seen = new Set();
  const rows = parsed.map((values, index) => {
    const line = index + 2;
    if (values.length !== headers.length) throw new Error(`La lectura ${line} no tiene el mismo número de columnas que la cabecera.`);
    const record = Object.fromEntries(headers.map((name, i) => [name, values[i]]));
    record.asset_id = record.asset_id.trim();
    if (!record.asset_id) throw new Error(`Falta la máquina en la lectura ${line}.`);
    const date = parseTimestamp(record.timestamp.trim());
    const key = JSON.stringify([record.asset_id, date.key]);
    if (seen.has(key)) throw new Error(`Hay lecturas duplicadas para una misma máquina y fecha (lectura ${line}).`);
    seen.add(key);
    record.timestamp = date.iso;
    record._time = date.millis;
    for (const name of numeric) {
      const value = record[name].trim();
      if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value) || !Number.isFinite(Number(value))) throw new Error(`La columna ${name} contiene un valor vacío o no numérico en la lectura ${line}.`);
      record[name] = Number(value);
    }
    if (record.operating_hours < 0) throw new Error(`Las horas de uso no pueden ser negativas (lectura ${line}).`);
    return record;
  });
  rows.sort((a, b) => a.asset_id.localeCompare(b.asset_id) || a._time - b._time);
  return { headers, rows, sensors, assets: [...new Set(rows.map(row => row.asset_id))] };
}

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  const number = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 3 });
  const date = new Intl.DateTimeFormat('es-ES', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' });
  let dataset;
  let loadVersion = 0;
  const svgNS = 'http://www.w3.org/2000/svg';
  function node(tag, attributes = {}, content) {
    const element = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (content !== undefined) element.textContent = content;
    return element;
  }
  function showMessage(text, error = false) { $('message').textContent = text; $('message').classList.toggle('error', error); }
  function options(select, values, label) {
    select.replaceChildren(...values.map(value => { const option = document.createElement('option'); option.value = value; option.textContent = label(value); return option; }));
  }
  function renderChart() {
    if (!dataset) return;
    const asset = $('asset-select').value, sensor = $('sensor-select').value;
    const rows = dataset.rows.filter(row => row.asset_id === asset);
    const info = SENSOR_INFO[sensor], svg = $('chart');
    const title = node('title', { id: 'chart-title' }, `${info.label} de ${asset}`);
    const description = node('desc', { id: 'chart-desc' }, `${rows.length} lecturas. Unidad: ${info.unit}. Fechas en UTC.`);
    svg.replaceChildren(title, description);
    const minTime = rows[0]._time, maxTime = rows[rows.length - 1]._time;
    let minValue = Infinity, maxValue = -Infinity;
    for (const row of rows) { minValue = Math.min(minValue, row[sensor]); maxValue = Math.max(maxValue, row[sensor]); }
    const pad = (maxValue - minValue || Math.max(Math.abs(maxValue) * .1, 1)) * .15;
    minValue -= pad; maxValue += pad;
    const x = time => 75 + ((time - minTime) / (maxTime - minTime || 1)) * 855;
    const y = value => 260 - ((value - minValue) / (maxValue - minValue)) * 225;
    for (let tick = 0; tick <= 4; tick++) {
      const value = minValue + (maxValue - minValue) * tick / 4, position = y(value);
      svg.append(node('line', { x1: 75, y1: position, x2: 930, y2: position, stroke: '#e5edef', 'stroke-width': 1 }));
      svg.append(node('text', { x: 61, y: position + 4, 'text-anchor': 'end', fill: '#6b818a', 'font-size': 11 }, number.format(value)));
    }
    svg.append(node('text', { x: 75, y: 18, fill: '#50717c', 'font-size': 11 }, info.unit));
    svg.append(node('text', { x: 75, y: 286, fill: '#6b818a', 'font-size': 11 }, date.format(minTime)));
    if (maxTime !== minTime) svg.append(node('text', { x: 930, y: 286, 'text-anchor': 'end', fill: '#6b818a', 'font-size': 11 }, date.format(maxTime)));
    let sampled = rows;
    if (rows.length > 1600) {
      sampled = [rows[0]];
      const stride = Math.ceil(rows.length / 790);
      for (let start = 1; start < rows.length - 1; start += stride) {
        const bucket = rows.slice(start, Math.min(start + stride, rows.length - 1));
        let low = bucket[0], high = bucket[0];
        for (const row of bucket) { if (row[sensor] < low[sensor]) low = row; if (row[sensor] > high[sensor]) high = row; }
        sampled.push(...(low._time <= high._time ? [low, high] : [high, low]));
      }
      sampled.push(rows[rows.length - 1]);
    }
    const points = sampled.map(row => `${x(row._time)},${y(row[sensor])}`).join(' ');
    if (rows.length > 1) {
      svg.append(node('polygon', { points: `${x(sampled[0]._time)},260 ${points} ${x(sampled[sampled.length - 1]._time)},260`, fill: '#e8f4ef' }));
      svg.append(node('polyline', { points, fill: 'none', stroke: '#0c8271', 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    }
    if (rows.length <= 60) for (const row of rows) svg.append(node('circle', { cx: x(row._time), cy: y(row[sensor]), r: 4, fill: '#0c8271', stroke: '#fff', 'stroke-width': 2 }));
    $('chart-description').textContent = `${asset} · ${info.label} (${info.unit})`;
    $('chart-footnote').textContent = `${number.format(rows.length)} lecturas del equipo · Fechas en UTC.${sampled !== rows ? ' Gráfico reducido conservando extremos por intervalo.' : ''} Una variación no demuestra una avería.`;
  }
  function display(text, label) {
    dataset = undefined;
    $('results').hidden = true;
    try {
      dataset = validateCSV(text);
      const { rows, headers, assets, sensors } = dataset;
      let first = Infinity, last = -Infinity;
      for (const row of rows) { first = Math.min(first, row._time); last = Math.max(last, row._time); }
      $('readings-count').textContent = number.format(rows.length);
      $('assets-count').textContent = number.format(assets.length);
      $('period').textContent = `${date.format(first)} → ${date.format(last)}`;
      $('dataset-label').textContent = label;
      options($('asset-select'), assets, value => value);
      options($('sensor-select'), sensors, value => SENSOR_INFO[value].label);
      const head = document.createElement('tr');
      for (const header of headers) { const cell = document.createElement('th'); cell.scope = 'col'; cell.textContent = header; head.append(cell); }
      $('data-table').tHead.replaceChildren(head);
      $('data-table').tBodies[0].replaceChildren(...rows.slice(0, 100).map(row => {
        const tr = document.createElement('tr');
        for (const header of headers) { const cell = document.createElement('td'); cell.textContent = typeof row[header] === 'number' ? number.format(row[header]) : row[header]; tr.append(cell); }
        return tr;
      }));
      $('table-count').textContent = `${Math.min(rows.length, 100)} de ${number.format(rows.length)} lecturas`;
      $('results').hidden = false;
      renderChart();
      showMessage('CSV válido. Los datos están listos para explorar.');
    } catch (error) { showMessage(error.message || 'No se ha podido leer el archivo.', true); }
  }
  $('asset-select').addEventListener('change', renderChart);
  $('sensor-select').addEventListener('change', renderChart);
  $('demo-button').addEventListener('click', () => { loadVersion++; $('csv-file').value = ''; display(DEMO_CSV, 'Datos sintéticos de ejemplo'); });
  $('csv-file').addEventListener('change', async event => {
    const version = ++loadVersion, file = event.target.files[0];
    if (!file) return;
    if (file.size > MAX_BYTES) { $('results').hidden = true; dataset = undefined; showMessage('El archivo supera el límite de 10 MiB.', true); return; }
    showMessage('Leyendo y validando el archivo…');
    try {
      const content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
      if (version === loadVersion) display(content, file.name);
    } catch (error) {
      if (version === loadVersion) { $('results').hidden = true; dataset = undefined; showMessage('No se ha podido leer el archivo. Utiliza un CSV guardado como UTF-8.', true); }
    }
  });
  display(DEMO_CSV, 'Datos sintéticos de ejemplo');
}
