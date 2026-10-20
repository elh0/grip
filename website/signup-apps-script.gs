// Grip signups: paste into the "Grip signups" Google Sheet (Extensions > Apps Script), then Deploy > New deployment > Web app,
// Execute as: Me, Who has access: Anyone. The site posts email + type (beta/coach) here; each one becomes a row.
function doPost(e) {
  var p = (e && e.parameter) || {};
  var email = String(p.email || '').trim().slice(0, 200);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return ContentService.createTextOutput('bad email');
  var type = p.type === 'coach' ? 'coach' : 'beta';
  var lock = LockService.getScriptLock(); lock.waitLock(10000);
  try { SpreadsheetApp.getActiveSpreadsheet().getSheets()[0].appendRow([new Date(), email, type, String(p.page || '').slice(0, 200)]); }
  finally { lock.releaseLock(); }
  return ContentService.createTextOutput('ok');
}
