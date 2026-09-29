// «Apoya este proyecto»: Payment Link de Stripe (MXN, monto libre; Apple Pay, Google Pay, tarjeta y OXXO).
// Un solo lugar para el enlace: lo usan los pies de todas las páginas y los avisos del Laboratorio.
// Mientras APOYO_URL esté vacío, los enlaces siguen en «#».
(function () {
  'use strict';
  var APOYO_URL = 'https://buy.stripe.com/test_7sYfZb1hpc3ifE8aQMafS00'; // PRUEBA (sandbox): cambiar por el enlace real al activar Stripe
  if (!APOYO_URL) return;
  document.querySelectorAll('a[data-pendiente="cafe"]').forEach(function (a) {
    a.href = APOYO_URL; a.target = '_blank'; a.rel = 'noopener'; a.removeAttribute('data-pendiente');
  });
})();
