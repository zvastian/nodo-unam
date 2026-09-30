// «Apoya este proyecto»: Payment Link de Stripe (MXN, monto libre; Apple Pay, Google Pay, tarjeta y OXXO).
// Un solo lugar para el enlace: lo usan los pies de todas las páginas y los avisos del Laboratorio.
// Mientras APOYO_URL esté vacío (v4.39.1: el sitio se abrió antes de activar Stripe en modo real), se
// ocultan los enlaces y la invitación a apoyar ([data-apoyo]): el checkout de prueba no se muestra en público.
(function () {
  'use strict';
  var APOYO_URL = 'https://buy.stripe.com/eVqcMZg8E3t961u3dS4gg00'; // Payment Link de Stripe en modo real (v4.39.2)
  if (!APOYO_URL) {
    document.querySelectorAll('a[data-pendiente="cafe"]').forEach(function (a) { (a.closest('li') || a).hidden = true; });
    document.querySelectorAll('[data-apoyo]').forEach(function (e) { e.hidden = true; });
    return;
  }
  document.querySelectorAll('a[data-pendiente="cafe"]').forEach(function (a) {
    a.href = APOYO_URL; a.target = '_blank'; a.rel = 'noopener'; a.removeAttribute('data-pendiente');
  });
})();
