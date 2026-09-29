// Ajustes de NodOS (v4.26): la misma ventana en el mapa, el Laboratorio y Mi espacio.
// Apariencia (día o noche) y color de los puntos del mapa (campos o áreas). Cada página pone
// lo suyo al cambiar: NodosAjustes.montar({ boton, alModo(oscuro), alLente(lente) }).
(function () {
  'use strict';
  var CLAVE_MODO = 'nodo_noche', CLAVE_LENTE = 'nodo_lente';
  function leer(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function escribir(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin almacenamiento: solo esta sesión */ } }

  // muestras: los tonos de la paleta de campos del mapa (buildPalette) y las cuatro áreas
  function tiraCampos() {
    var s = '';
    for (var i = 0; i < 16; i++) {
      var r = i % 3, h = (i * 22.5 + 150) % 360;
      s += '<i class="aj-c' + r + '" style="--h:' + h.toFixed(1) + '"></i>';
    }
    return s;
  }
  var tiraAreas = '<i class="aj-a1"></i><i class="aj-a2"></i><i class="aj-a3"></i><i class="aj-a4"></i>';
  var ICO_X = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>';

  var HTML =
    '<div class="aj-banda"><h3 id="aj-titulo">Ajustes</h3>' +
      '<button type="button" class="aj-cerrar" aria-label="Cerrar ajustes">' + ICO_X + '</button></div>' +
    '<section class="aj-sec"><h4 id="aj-h-modo">Apariencia</h4>' +
      '<div class="aj-modos" role="radiogroup" aria-labelledby="aj-h-modo">' +
        '<button type="button" role="radio" data-modo="claro"><img src="ventanas-dia.svg" width="96" height="96" alt=""><span class="aj-op"><span class="aj-radio"></span>Día</span></button>' +
        '<button type="button" role="radio" data-modo="oscuro"><img src="ventanas-noche.svg" width="96" height="96" alt=""><span class="aj-op"><span class="aj-radio"></span>Noche</span></button>' +
      '</div></section>' +
    '<section class="aj-sec"><h4 id="aj-h-lente">Color de los puntos del mapa</h4>' +
      '<div class="aj-lentes" role="radiogroup" aria-labelledby="aj-h-lente">' +
        '<button type="button" role="radio" data-lente="territory"><span class="aj-radio"></span><span class="aj-txt"><b>Campos</b><small>Un color por cada uno de los 130 campos temáticos</small><span class="aj-tira">' + tiraCampos() + '</span></span></button>' +
        '<button type="button" role="radio" data-lente="area"><span class="aj-radio"></span><span class="aj-txt"><b>Áreas administrativas</b><small>Las cuatro áreas del catálogo de la UNAM</small><span class="aj-tira aj-tira-areas">' + tiraAreas + '</span></span></button>' +
      '</div></section>';

  var caja, capa, boton, op = {}, antes = null;
  function oscuro() { return leer(CLAVE_MODO) === '1'; }
  function lente() { return leer(CLAVE_LENTE) === 'area' ? 'area' : 'territory'; }
  function pintar() {
    if (!caja) return;
    var o = op.modo ? op.modo() : oscuro(), l = op.lente ? op.lente() : lente();
    caja.querySelectorAll('[data-modo]').forEach(function (b) { b.setAttribute('aria-checked', String((b.dataset.modo === 'oscuro') === o)); });
    caja.querySelectorAll('[data-lente]').forEach(function (b) { b.setAttribute('aria-checked', String(b.dataset.lente === l)); });
  }
  function abrir(si) {
    var on = si === undefined ? caja.hidden : si;
    if (on) { antes = document.activeElement; pintar(); }
    caja.hidden = !on; capa.hidden = !on;
    if (boton) boton.setAttribute('aria-expanded', String(on));
    if (on) caja.querySelector('[aria-checked="true"]').focus();
    else if (antes && antes.focus) antes.focus();
  }
  function montar(o) {
    op = o || {};
    boton = op.boton || null;
    capa = document.createElement('div'); capa.className = 'aj-capa'; capa.hidden = true;
    caja = document.createElement('div'); caja.className = 'aj'; caja.id = 'ajustes'; caja.hidden = true;
    caja.setAttribute('role', 'dialog'); caja.setAttribute('aria-modal', 'true'); caja.setAttribute('aria-labelledby', 'aj-titulo');
    caja.innerHTML = HTML;
    document.body.appendChild(capa); document.body.appendChild(caja);
    if (boton) { boton.setAttribute('aria-haspopup', 'dialog'); boton.setAttribute('aria-expanded', 'false'); boton.addEventListener('click', function (ev) { ev.stopPropagation(); abrir(); }); }
    capa.addEventListener('click', function () { abrir(false); });
    caja.querySelector('.aj-cerrar').addEventListener('click', function () { abrir(false); });
    caja.addEventListener('click', function (ev) {
      var m = ev.target.closest('[data-modo]'), l = ev.target.closest('[data-lente]');
      if (m) { var os = m.dataset.modo === 'oscuro'; escribir(CLAVE_MODO, os ? '1' : '0'); if (op.alModo) op.alModo(os); pintar(); }
      if (l) { escribir(CLAVE_LENTE, l.dataset.lente); if (op.alLente) op.alLente(l.dataset.lente); pintar(); }
    });
    // flechas dentro de cada grupo, como un grupo de radios
    caja.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { ev.stopPropagation(); abrir(false); return; }
      var g = ev.target.closest('[role="radiogroup"]'); if (!g || !/^Arrow/.test(ev.key)) return;
      var bs = Array.prototype.slice.call(g.querySelectorAll('[role="radio"]')), i = bs.indexOf(ev.target);
      var j = (i + (ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length;
      ev.preventDefault(); bs[j].focus(); bs[j].click();
    });
    pintar();
  }
  window.NodosAjustes = { montar: montar, abrir: abrir, pintar: pintar, oscuro: oscuro, lente: lente, abierto: function () { return !!caja && !caja.hidden; } };
})();
