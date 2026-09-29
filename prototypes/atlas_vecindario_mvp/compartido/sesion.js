// NodOS: sesión compartida del mapa, el Laboratorio y Mi espacio (sin build; se carga después de
// supabase-js). Supabase Auth con Google, GitHub y enlace por correo (PKCE); la sesión vive en este
// navegador. Pinta en la barra «Entrar» o la inicial con su menú, más «Mi espacio»; trae la pantalla
// de acceso (el componente y su ventana) y las llamadas al Worker con el token.
// La clave publicable es pública por diseño.
(function () {
  'use strict';
  var SUPABASE_URL = 'https://vujmkcpxsdrmrwsijnlz.supabase.co', SUPABASE_KEY = 'sb_publishable_R75esEpJeDH4QopgUKWoXg_DF9ocOYE';
  var PARAM = new URLSearchParams(location.search);
  var LOCAL = /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
  // ?puerta= solo en local: en producción, un enlace con ?puerta=https://otro-sitio mandaría ahí
  // el token de sesión. Publicado, la API está en el mismo origen (nodosmap.com/api/*, la ruta del
  // Worker «puerta»), que es lo único que la CSP deja llamar (connect-src 'self').
  var PUERTA = LOCAL ? (PARAM.get('puerta') || 'http://127.0.0.1:8787') : location.origin;
  var sb = null, usuario = null, oyentes = [], listoOk = null, primera = true;
  var listo = new Promise(function (r) { listoOk = r; });
  try {
    if (window.supabase) sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, { auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true } });
  } catch (err) { console.error('No se pudo iniciar la sesión', err); }

  function $(id) { return document.getElementById(id); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function aDonde() { return location.origin + location.pathname; }

  // ---------- acceso: el componente (ventana de la barra e invitaciones de cada página) ----------
  var G_LOGO = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>';
  var GH_LOGO = '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>';
  var PROVEEDOR = { google: 'Google', github: 'GitHub' };

  function aviso(txt) { document.querySelectorAll('.acceso-aviso').forEach(function (p) { p.textContent = txt; }); }
  function marcar(clave) { if (!clave) return; try { localStorage.setItem(clave, '1'); } catch (e) { /* sin almacenamiento */ } }
  function desmarcar(clave) { if (!clave) return; try { localStorage.removeItem(clave); } catch (e) { /* sin almacenamiento */ } }
  // «marca»: clave de almacenamiento que la página lee al volver (p. ej., el análisis que arranca solo)
  function entrarProveedor(prov, marca) {
    if (!sb) { aviso('No se pudo conectar con el inicio de sesión. Revisa tu conexión e inténtalo de nuevo.'); return; }
    marcar(marca);
    sb.auth.signInWithOAuth({ provider: prov, options: { redirectTo: aDonde() } }).then(function (r) {
      if (r.error) { desmarcar(marca); aviso('No se pudo abrir ' + PROVEEDOR[prov] + ': ' + r.error.message); }
    });
  }
  function entrarCorreo(correo, marca) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)) { aviso('Escribe un correo válido, como nombre@correo.com.'); return false; }
    if (!sb) { aviso('No se pudo conectar con el inicio de sesión. Revisa tu conexión e inténtalo de nuevo.'); return false; }
    marcar(marca); aviso('Enviando…');
    sb.auth.signInWithOtp({ email: correo, options: { emailRedirectTo: aDonde(), shouldCreateUser: true } }).then(function (r) {
      if (r.error) { desmarcar(marca); aviso(/rate|limit/i.test(r.error.message) ? 'Se enviaron demasiados enlaces en poco tiempo. Espera unos minutos.' : 'No se pudo enviar el enlace: ' + r.error.message); return; }
      aviso('');
      document.querySelectorAll('.acceso').forEach(function (a) {
        a.classList.add('enviado');
        a.querySelector('.acceso-enviado p').innerHTML = 'Te enviamos un enlace a <b>' + esc(correo) + '</b>. Ábrelo en este mismo navegador para entrar.';
      });
    });
    return true;
  }
  function pintarAcceso(cont, marca) {
    var id = cont.id || ('acc' + Math.random().toString(36).slice(2, 7));
    cont.innerHTML = '<div class="acceso">' +
      '<button type="button" class="btn-google" data-prov="google">' + G_LOGO + '<span>Continuar con Google</span></button>' +
      '<button type="button" class="btn-google btn-github" data-prov="github">' + GH_LOGO + '<span>Continuar con GitHub</span></button>' +
      '<div class="o-sep">o</div>' +
      '<form class="acceso-correo" novalidate onsubmit="return false"><label class="oculto" for="' + id + '-email">Correo</label>' +
        '<input id="' + id + '-email" class="campo-caja" type="email" autocomplete="email" placeholder="tu@correo.com">' +
        '<button type="submit" class="btn-cta">Continuar con correo</button></form>' +
      '<p class="acceso-aviso" aria-live="polite"></p>' +
      '<div class="acceso-enviado" aria-live="polite"><svg viewBox="0 0 40 40" aria-hidden="true"><rect x="5" y="9" width="30" height="22" rx="2"/><path d="M6 11l14 11 14-11"/></svg>' +
        '<h4>Revisa tu correo</h4><p></p><button type="button" class="btn-txt acceso-otro">Usar otro correo</button></div>' +
      '<p class="acceso-legal">Con el correo te enviamos un enlace para entrar, sin contraseña. Al continuar aceptas los <a href="terminos.html">términos de uso</a> y el <a href="privacidad.html">aviso de privacidad</a>.</p>' +
    '</div>';
    var a = cont.querySelector('.acceso');
    a.querySelectorAll('[data-prov]').forEach(function (b) { b.addEventListener('click', function () { entrarProveedor(b.getAttribute('data-prov'), marca); }); });
    a.querySelector('.acceso-correo').addEventListener('submit', function () { var i = a.querySelector('.campo-caja'); if (!entrarCorreo(i.value.trim(), marca)) i.focus(); });
    a.querySelector('.acceso-otro').addEventListener('click', function () { a.classList.remove('enviado'); aviso(''); a.querySelector('.campo-caja').focus(); });
    return a;
  }

  // ---------- la ventana «Entra a NodOS» (una sola, la inserta este módulo) ----------
  var desde = null;
  function crearVentana() {
    if ($('nds-entrar')) return;
    var capa = document.createElement('div'); capa.className = 'nds-capa'; capa.id = 'nds-capa'; capa.hidden = true;
    var dlg = document.createElement('div'); dlg.className = 'nds-dlg'; dlg.id = 'nds-entrar'; dlg.hidden = true;
    dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'true'); dlg.setAttribute('aria-labelledby', 'nds-entrar-titulo');
    dlg.innerHTML = '<button type="button" class="nds-cerrar" id="nds-cerrar" aria-label="Cerrar"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/></svg></button>' +
      '<div class="acceso-cab"><span class="acceso-logo" id="nds-logo" aria-hidden="true"></span><h3 id="nds-entrar-titulo">Entra a NodOS</h3><p>Guarda tus análisis, las tesis, los asesores y los temas del mapa, y vuelve a ellos cuando quieras.</p></div>' +
      '<div id="nds-acceso"></div>';
    document.body.appendChild(capa); document.body.appendChild(dlg);
    var marca = document.querySelector('header .brand-logo'); if (marca) $('nds-logo').appendChild(marca.cloneNode(true));
    pintarAcceso($('nds-acceso'), null);
    capa.addEventListener('click', cerrarEntrar); $('nds-cerrar').addEventListener('click', cerrarEntrar);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !dlg.hidden) cerrarEntrar(); });
    // Tab no sale de la ventana (v4.38.5)
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab' || dlg.hidden) return;
      var f = Array.prototype.filter.call(dlg.querySelectorAll('a[href], button:not([disabled]), input:not([disabled])'), function (x) { return x.offsetParent !== null; });
      if (!f.length) return;
      var a0 = f[0], z = f[f.length - 1];
      if (!dlg.contains(document.activeElement)) { e.preventDefault(); a0.focus(); }
      else if (e.shiftKey && document.activeElement === a0) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a0.focus(); }
    }, true);
  }
  function abrirEntrar(origen) {
    crearVentana(); aviso(''); desde = origen || document.activeElement;
    $('nds-capa').hidden = false; $('nds-entrar').hidden = false;
    var g = $('nds-entrar').querySelector('.btn-google'); if (g) g.focus();
  }
  function cerrarEntrar() {
    if (!$('nds-entrar') || $('nds-entrar').hidden) return;
    $('nds-capa').hidden = true; $('nds-entrar').hidden = true;
    if (desde && desde.focus) desde.focus();
  }

  // ---------- la barra: «Mi espacio» y luego «Entrar» o la inicial con su menú (v4.31.1) ----------
  function pintarNav() {
    var c = document.querySelector('[data-nds-cuenta]'); if (!c) return;
    var enEspacio = /espacio\.html$/.test(location.pathname);
    if (!c.dataset.hecho) {
      c.dataset.hecho = '1';
      c.innerHTML = '<a class="nds-espacio' + (enEspacio ? ' activo' : '') + '" href="espacio.html" aria-label="Mi espacio" title="Mi espacio"' + (enEspacio ? ' aria-current="page"' : '') + '><svg class="ico-nav" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 11 12 2.75 21.5 11"/><path d="M5 9v12.25h5v-6.5h4v6.5h5V9"/></svg></a>' +
        '<button type="button" class="nds-entrar" id="nds-btn-entrar" aria-haspopup="dialog" aria-label="Entrar" title="Entrar" hidden><svg class="ico-nav" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.25" r="4.5"/><path d="M3.5 21.25c0-4.9 3.8-8 8.5-8s8.5 3.1 8.5 8"/></svg></button>' +
        '<div class="nds-cuenta" id="nds-cuenta" hidden><button type="button" class="nds-ini" id="nds-ini" aria-haspopup="menu" aria-expanded="false"></button>' +
          '<div class="nds-menu" id="nds-menu" role="menu" hidden><p class="nds-correo" id="nds-correo"></p><button type="button" role="menuitem" id="nds-salir">Salir</button></div></div>';
      $('nds-btn-entrar').addEventListener('click', function () { abrirEntrar(this); });
      $('nds-ini').addEventListener('click', function (e) { e.stopPropagation(); menu($('nds-menu').hidden); });
      $('nds-salir').addEventListener('click', function () { menu(false); if (sb) sb.auth.signOut(); });
      document.addEventListener('click', function (e) { if (!$('nds-menu').hidden && !e.target.closest('#nds-cuenta')) menu(false); });
    }
    $('nds-btn-entrar').hidden = !!usuario || !sb; $('nds-cuenta').hidden = !usuario;
    if (usuario) {
      $('nds-ini').textContent = (usuario.email || '?').charAt(0).toUpperCase();
      $('nds-ini').setAttribute('aria-label', 'Tu cuenta: ' + (usuario.email || ''));
      $('nds-correo').textContent = usuario.email || '';
    }
  }
  function menu(abrir) { $('nds-menu').hidden = !abrir; $('nds-ini').setAttribute('aria-expanded', String(!!abrir)); }

  // ---------- estado de la sesión ----------
  function poner(ses) {
    var antes = usuario && usuario.id;
    usuario = ses ? { id: ses.user && ses.user.id, email: (ses.user && ses.user.email) || '', token: ses.access_token } : null;
    pintarNav();
    if (usuario) cerrarEntrar();
    if ((usuario && usuario.id) !== antes || primera) {
      guardados.tesis = new Set(); guardados.asesores = new Set(); guardados.lugares = new Set();
      var carga = usuario ? cargarGuardados() : Promise.resolve();
      carga.then(function () {
        oyentes.forEach(function (f) { try { f(usuario); } catch (e) { console.error(e); } });
        if (primera) { primera = false; listoOk(usuario); }
      });
    } else {
      oyentes.forEach(function (f) { try { f(usuario); } catch (e) { console.error(e); } });
    }
  }

  // ---------- el Worker: llamadas con el token ----------
  function api(ruta, op) {
    op = op || {};
    if (!usuario) { var e0 = new Error('sin_sesion'); e0.status = 401; e0.codigo = 'sin_sesion'; return Promise.reject(e0); }
    if (!PUERTA) { var e1 = new Error('sin_servicio'); e1.status = 0; e1.codigo = 'sin_servicio'; return Promise.reject(e1); }
    var h = { Authorization: 'Bearer ' + usuario.token };
    if (op.cuerpo !== undefined) h['Content-Type'] = 'application/json';
    return fetch(PUERTA + ruta, { method: op.metodo || 'GET', headers: Object.assign(h, op.cab || {}), body: op.cuerpo === undefined ? undefined : JSON.stringify(op.cuerpo) })
      .then(function (r) {
        return r.text().then(function (t) {
          var j = null; try { j = t ? JSON.parse(t) : null; } catch (e) { j = null; }
          if (!r.ok) { var err = new Error((j && j.error) || ('HTTP ' + r.status)); err.status = r.status; err.codigo = j && j.error; err.datos = j; throw err; }
          return j;
        });
      });
  }
  // lo guardado: los ids de tesis y las claves de asesores, para marcar los botones de cada página
  var guardados = { tesis: new Set(), asesores: new Set(), lugares: new Set() };
  function claveAsesor(nombre) {
    return String(nombre || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
      .replace(/[^a-z0-9 .'-]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 160);
  }
  function cargarGuardados() {
    return Promise.all([
      api('/api/tesis').then(function (j) { guardados.tesis = new Set(((j && j.tesis) || []).map(function (t) { return t.tesis; })); }),
      api('/api/asesores').then(function (j) { guardados.asesores = new Set(((j && j.asesores) || []).map(function (a) { return a.asesor; })); }),
      api('/api/lugares').then(function (j) { guardados.lugares = new Set(((j && j.lugares) || []).map(function (l) { return l.lugar; })); })
    ]).catch(function (err) { console.warn('No se pudo leer lo guardado:', err.codigo || err.message); });
  }
  function guardarTesis(id, datos, si) {
    return api('/api/tesis/' + encodeURIComponent(id), si ? { metodo: 'PUT', cuerpo: datos || {} } : { metodo: 'DELETE' })
      .then(function () { if (si) guardados.tesis.add(id); else guardados.tesis.delete(id); });
  }
  // «Guardar las N»: bloques de 100 por petición (PUT /api/tesis), no una petición por tesis, que
  // chocaba con el límite por IP. items: [{ id, datos }]. alBloque(ids) marca cada bloque al llegar.
  // Resuelve con los ids guardados; si se llegó al límite, rechaza con codigo «limite_de_tesis»
  // después de marcar los que sí entraron.
  var LOTE = 100;
  function guardarTesisLote(items, alBloque) {
    var guardadas = [], i = 0;
    function siguiente() {
      if (i >= items.length) return Promise.resolve(guardadas);
      var bloque = items.slice(i, i + LOTE); i += LOTE;
      return api('/api/tesis', { metodo: 'PUT', cuerpo: { tesis: bloque.map(function (t) { return { id: t.id, datos: t.datos || {} }; }) } })
        .then(function (j) {
          var ids = (j && j.guardadas) || [];
          ids.forEach(function (id) { guardados.tesis.add(id); guardadas.push(id); });
          if (alBloque) alBloque(ids);
          if (j && j.error) { var e = new Error(j.error); e.codigo = j.error; e.datos = j; throw e; }
          return siguiente();
        });
    }
    return siguiente();
  }
  function guardarAsesor(nombre, datos, si) {
    var k = claveAsesor(nombre);
    return api('/api/asesores/' + encodeURIComponent(k), si ? { metodo: 'PUT', cuerpo: Object.assign({ nombre: nombre }, datos || {}) } : { metodo: 'DELETE' })
      .then(function () { if (si) guardados.asesores.add(k); else guardados.asesores.delete(k); });
  }
  // lugar del mapa: «macro:31», «meso:31.C4», «micro:31.U281»
  function guardarLugar(clave, datos, si) {
    return api('/api/lugares/' + encodeURIComponent(clave), si ? { metodo: 'PUT', cuerpo: datos || {} } : { metodo: 'DELETE' })
      .then(function () { if (si) guardados.lugares.add(clave); else guardados.lugares.delete(clave); });
  }
  // todo lo guardado con sus datos, para listas (Mi espacio y el marcador del mapa)
  function listaGuardados() {
    return Promise.all([api('/api/tesis'), api('/api/asesores'), api('/api/lugares')]).then(function (r) {
      var o = { tesis: (r[0] && r[0].tesis) || [], asesores: (r[1] && r[1].asesores) || [], lugares: (r[2] && r[2].lugares) || [] };
      guardados.tesis = new Set(o.tesis.map(function (t) { return t.tesis; }));
      guardados.asesores = new Set(o.asesores.map(function (a) { return a.asesor; }));
      guardados.lugares = new Set(o.lugares.map(function (l) { return l.lugar; }));
      return o;
    });
  }

  // ---------- el marcador al guardar: salta y se llena; al quitar, se vacía ----------
  function animarGuardado(el, on) {
    if (!el) return;
    el.classList.remove('nds-pop', 'nds-suelta'); void el.offsetWidth;
    el.classList.add(on ? 'nds-pop' : 'nds-suelta');
    clearTimeout(el._ndsT); el._ndsT = setTimeout(function () { el.classList.remove('nds-pop', 'nds-suelta'); }, 600);
  }

  // ---------- confirmar antes de borrar: «¿Deseas borrar …?», Sí / No y «No preguntar la próxima vez» ----------
  var PREGUNTA = 'nodo_confirmar_borrar';
  function preguntar() { try { return localStorage.getItem(PREGUNTA) !== '0'; } catch (e) { return true; } }
  function fijarPreguntar(si) { try { localStorage.setItem(PREGUNTA, si ? '1' : '0'); } catch (e) { /* sin almacenamiento: se pregunta siempre */ } }
  // op: { titulo, pregunta, nota, si, recordar }. «recordar» ofrece dejar de preguntar (no para la cuenta).
  function confirmar(op) {
    op = op || {};
    if (op.recordar && !preguntar()) return Promise.resolve(true);
    crearVentana();
    var capa = $('nds-capa'), dlg = document.createElement('div'), antes = document.activeElement;
    dlg.className = 'nds-dlg nds-conf'; dlg.setAttribute('role', 'alertdialog'); dlg.setAttribute('aria-modal', 'true');
    dlg.setAttribute('aria-labelledby', 'nds-conf-q');
    dlg.innerHTML = '<p class="conf-q" id="nds-conf-q">' + (op.pregunta ? esc(op.pregunta) : '¿Deseas borrar <b>' + esc(op.titulo || 'este elemento') + '</b>?') + '</p>' +
      (op.nota ? '<p class="conf-nota">' + esc(op.nota) + '</p>' : '') +
      '<div class="conf-botones"><button type="button" class="conf-si">' + esc(op.si || 'Sí, borrar') + '</button><button type="button" class="conf-no">No</button></div>' +
      (op.recordar ? '<label class="conf-recordar"><input type="checkbox" role="switch"><span class="conf-switch" aria-hidden="true"></span>No preguntar la próxima vez</label>' : '');
    document.body.appendChild(dlg); capa.hidden = false;
    return new Promise(function (listo) {
      function fin(si) {
        if (si && op.recordar && dlg.querySelector('.conf-recordar input').checked) fijarPreguntar(false);
        document.removeEventListener('keydown', tecla, true); capa.removeEventListener('click', no);
        dlg.remove(); capa.hidden = $('nds-entrar').hidden;
        if (antes && antes.focus && document.contains(antes)) antes.focus();
        listo(si);
      }
      function no() { fin(false); }
      function tecla(e) {
        if (e.key === 'Escape') { e.stopPropagation(); fin(false); }
        else if (e.key === 'Tab') { // el foco no sale de la ventana
          var f = dlg.querySelectorAll('button, input'), a = f[0], z = f[f.length - 1];
          if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
        }
      }
      dlg.querySelector('.conf-si').addEventListener('click', function () { fin(true); });
      dlg.querySelector('.conf-no').addEventListener('click', no);
      capa.addEventListener('click', no);
      document.addEventListener('keydown', tecla, true);
      dlg.querySelector('.conf-no').focus(); // lo seguro, por omisión
    });
  }

  window.NodOS = {
    PUERTA: PUERTA,
    usuario: function () { return usuario; },
    listo: listo,
    alCambiar: function (f) { oyentes.push(f); },
    abrirEntrar: abrirEntrar, cerrarEntrar: cerrarEntrar,
    pintarAcceso: pintarAcceso, aviso: aviso,
    api: api,
    guardados: guardados, claveAsesor: claveAsesor, guardarTesis: guardarTesis, guardarTesisLote: guardarTesisLote, guardarAsesor: guardarAsesor,
    guardarLugar: guardarLugar, listaGuardados: listaGuardados, animarGuardado: animarGuardado,
    confirmar: confirmar, preguntar: preguntar, fijarPreguntar: fijarPreguntar,
    salir: function () { if (sb) return sb.auth.signOut(); },
    borrarCuenta: function () { return api('/api/cuenta', { metodo: 'DELETE' }).then(function () { if (sb) return sb.auth.signOut(); }); }
  };

  // enlace para saltar la barra (v4.38.5): apunta al <main> de la página, que recibe el foco al usarlo
  function saltar() {
    var m = document.querySelector('main'); if (!m || document.querySelector('.saltar')) return;
    if (!m.id) m.id = 'nds-contenido';
    m.setAttribute('tabindex', '-1');
    var a = document.createElement('a'); a.className = 'saltar'; a.href = '#' + m.id; a.textContent = 'Saltar al contenido';
    document.body.insertBefore(a, document.body.firstChild);
  }
  function arrancar() {
    saltar();
    pintarNav();
    if (!sb) { listoOk(null); primera = false; return; }
    sb.auth.onAuthStateChange(function (ev, ses) { poner(ses); });
    sb.auth.getSession().then(function (r) { poner(r.data && r.data.session); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrancar); else arrancar();
})();
