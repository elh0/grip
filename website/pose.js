  /* ---- pose scenes (19 Oct 2026): hand-keyed moves that read as real technique, drawn in the tracked-body style.
     Elliot: the straight-wall ladder climber "is not how you do it"; show a heel hook, a proper roll, a strict muscle-up.
     Each figure is keyframes of 11 joints in a 100-unit side view; far limbs dimmed. ---- */
  var PBLUE = '{{LINE}}', PWHITE = '#F3F3F0';
  function pe(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function pAt(frames, t) {
    var i = 0; while (i < frames.length - 2 && t >= frames[i + 1][0]) i++;
    var a = frames[i], b = frames[i + 1], k = b[0] === a[0] ? 0 : Math.max(0, Math.min(1, (t - a[0]) / (b[0] - a[0]))), e = pe(k), o = {};
    for (var key in a[1]) { var p = a[1][key], q = b[1][key] || p; o[key] = [p[0] + (q[0] - p[0]) * e, p[1] + (q[1] - p[1]) * e]; }
    return o;
  }
  function pang(a, b, c) {
    var a1 = Math.atan2(a[1] - b[1], a[0] - b[0]), a2 = Math.atan2(c[1] - b[1], c[0] - b[0]), d = Math.abs(a1 - a2);
    if (d > Math.PI) d = 2 * Math.PI - d; return d * 180 / Math.PI;
  }
  function parc(a, b, c, r, lbl, side) {
    var a1 = Math.atan2(a[1] - b[1], a[0] - b[0]), a2 = Math.atan2(c[1] - b[1], c[0] - b[0]);
    var p1 = [b[0] + Math.cos(a1) * r, b[1] + Math.sin(a1) * r], p2 = [b[0] + Math.cos(a2) * r, b[1] + Math.sin(a2) * r];
    var sw = ((a2 - a1 + 4 * Math.PI) % (2 * Math.PI)) < Math.PI ? 1 : 0;
    return '<path d="M' + f(p1[0]) + ' ' + f(p1[1]) + 'A' + r + ' ' + r + ' 0 0 ' + sw + ' ' + f(p2[0]) + ' ' + f(p2[1]) + '" fill="none" stroke="' + PWHITE + '" stroke-width=".35"/>' +
      '<text x="' + f(b[0] + side * (r + 1.4)) + '" y="' + f(b[1] + .8) + '" text-anchor="' + (side < 0 ? 'end' : 'start') + '">' + Math.round(pang(a, b, c)) + '°</text>';
  }
  function pfig(J, col, op, ghost) {
    var far = ghost ? op : op * .42, s = '', w = ghost ? .5 : .9;
    var L = function (a, b, o) { return '<line x1="' + f(a[0]) + '" y1="' + f(a[1]) + '" x2="' + f(b[0]) + '" y2="' + f(b[1]) + '" stroke="' + col + '" stroke-opacity="' + o + '" stroke-width="' + w + '" stroke-linecap="round"' + (ghost ? ' stroke-dasharray="1 1"' : '') + '/>'; };
    var C = function (p, o) { return ghost ? '' : '<circle cx="' + f(p[0]) + '" cy="' + f(p[1]) + '" r=".75" fill="#000" stroke="' + col + '" stroke-opacity="' + o + '" stroke-width=".4"/>'; };
    s += L(J.N, J.eR, far) + L(J.eR, J.hR, far) + L(J.P, J.kR, far) + L(J.kR, J.fR, far);
    s += C(J.eR, far) + C(J.hR, far) + C(J.kR, far) + C(J.fR, far);
    s += L(J.N, J.P, op) + L(J.N, J.H, op);
    s += '<circle cx="' + f(J.H[0]) + '" cy="' + f(J.H[1]) + '" r="2.7" fill="#000" stroke="' + col + '" stroke-opacity="' + op + '" stroke-width="' + w + '"' + (ghost ? ' stroke-dasharray="1 1"' : '') + '/>';
    s += L(J.N, J.eL, op) + L(J.eL, J.hL, op) + L(J.P, J.kL, op) + L(J.kL, J.fL, op);
    s += C(J.N, op) + C(J.P, op) + C(J.eL, op) + C(J.hL, op) + C(J.kL, op) + C(J.fL, op);
    return s;
  }
  function pPin(at, dx, dy, a, b) {
    var x = at[0] + dx, y = at[1] + dy, end = dx < 0 ? 'end' : 'start';
    return '<line x1="' + f(at[0]) + '" y1="' + f(at[1]) + '" x2="' + f(x) + '" y2="' + f(y + 1) + '" stroke="' + PWHITE + '" stroke-opacity=".6" stroke-width=".3"/>' +
      '<text x="' + f(x + (dx < 0 ? -.6 : .6)) + '" y="' + f(y) + '" text-anchor="' + end + '">' + a + '</text>' +
      '<text x="' + f(x + (dx < 0 ? -.6 : .6)) + '" y="' + f(y + 2.4) + '" text-anchor="' + end + '" fill-opacity=".6">' + b + '</text>';
  }
  function farFill(k) { // calisthenics frames give one side only; derive the far side a touch behind
    for (var i = 0; i < k.length; i++) { var j = k[i][1]; ['e', 'h', 'k', 'f'].forEach(function (n) { if (!j[n + 'R']) j[n + 'R'] = [j[n + 'L'][0] + 1.3, j[n + 'L'][1] + .3]; }); }
    return k;
  }

  /* heel hook on a 25° overhang: match, heel up by the hands, pull through the heel, reach long */
  var WX = function (y) { return 28 + .44 * y; };
  var HK0 = { H: [33, 44.5], N: [36, 48], P: [47, 63], eL: [38, 41], hL: [43, 34], eR: [41, 42], hR: [43.5, 34.5], kR: [52, 71], fR: [60.6, 74], kL: [54, 62.5], fL: [58.8, 70] };
  var HK1 = { H: [31.5, 43], N: [35, 46.5], P: [46, 60], eL: [37.5, 40], hL: [43, 34], eR: [40, 41], hR: [43.5, 34.5], kR: [51, 69], fR: [60.6, 74], kL: [39, 51.5], fL: [46.5, 42] };
  var HK2 = { H: [29, 36], N: [32, 40], P: [42, 50], eL: [32, 31], hL: [34, 22], eR: [39, 42], hR: [43.5, 34.5], kR: [47, 58], fR: [50, 67], kL: [36, 43.5], fL: [46.5, 42] };
  var HK3 = { H: [28, 24], N: [31, 28], P: [40, 43], eL: [30, 20], hL: [33.3, 12], eR: [37, 33], hR: [43.5, 34.5], kR: [44, 52], fR: [46, 61], kL: [37.5, 35.5], fL: [46.5, 42] };
  var HOOK = { len: 11, frames: [[0, HK0], [1.2, HK0], [3, HK1], [5.2, HK2], [6.6, HK3], [8.6, HK3], [11, HK0]],
    notes: [[2.4, 'Heel in before you pull.', 'Right heel / knee at 38°'], [4.6, 'Drag the hips to the wall.', 'Hips 24cm off, best go 15cm'], [6.2, 'Reach long, don\'t snatch.', 'Left arm / lock-off at 64°']] };
  function hookWall(x0, x1, y0, y1) {
    var s = '<path d="M' + f(WX(y0 - 40)) + ' ' + (y0 - 40) + 'L' + f(WX(y1 + 40)) + ' ' + (y1 + 40) + 'L' + (x1 + 60) + ' ' + (y1 + 40) + 'L' + (x1 + 60) + ' ' + (y0 - 40) + 'Z" fill="#101111"/>';
    for (var g = -40; g < 160; g += 8) s += '<line x1="' + f(WX(g)) + '" y1="' + g + '" x2="' + (x1 + 60) + '" y2="' + f(g - (x1 + 60 - WX(g)) * .1) + '" stroke="#000" stroke-width=".4"/>';
    s += '<line x1="' + f(WX(y0 - 40)) + '" y1="' + (y0 - 40) + '" x2="' + f(WX(y1 + 40)) + '" y2="' + (y1 + 40) + '" stroke="' + PWHITE + '" stroke-opacity=".35" stroke-width=".35"/>';
    [[34, 4.6, 0], [42, 3.4, 1], [12, 4, 0], [74, 3, 1], [70, 2.6, 1], [-4, 3.6, 0], [26, 2.4, 1], [56, 3, 0], [88, 3.4, 1], [100, 2.6, 0]].forEach(function (h) {
      var x = WX(h[0]); s += '<path d="M' + f(x - h[1] * .9) + ' ' + f(h[0] - .4) + 'q' + f(h[1] * .3) + ' ' + f(-h[1] * .9) + ' ' + f(h[1] * 1.5) + ' ' + f(-h[1] * .2) + 'l.6 ' + f(h[1] * .6) + 'z" fill="none" stroke="' + PWHITE + '" stroke-opacity="' + (h[2] ? .35 : .6) + '" stroke-width=".35"/>';
    });
    return s;
  }
  var HROT = -10, HC = Math.cos(HROT * Math.PI / 180), HS = Math.sin(HROT * Math.PI / 180);
  function HR(p) { var x = p[0] - 45, y = p[1] - 50; return [45 + x * HC - y * HS, 50 + x * HS + y * HC]; }
  function wallCm(P) { return Math.abs(P[0] - WX(P[1])) / 1.0925 * 3; }

  /* jiu-jitsu, stood up (Elliot: keep it wrestling-style, hands on shoulders): collar tie, hand-fight, arm drag to the angle.
     You in blue on the left, partner in white */
  var TB0 = { H: [41, 47], N: [38, 52], P: [36, 72], eL: [48, 56], hL: [58, 51], eR: [45, 64], hR: [54, 62], kL: [33, 83], fL: [30, 94], kR: [41, 83], fR: [42, 94] };
  var TB1 = { H: [41, 48], N: [38, 53], P: [36, 72], eL: [48, 57], hL: [58, 52], eR: [43, 66], hR: [51, 70], kL: [33, 83], fL: [30, 94], kR: [42, 83], fR: [44, 94] };
  var TB2 = { H: [52, 48], N: [50, 54], P: [46, 73], eL: [55, 61], hL: [61, 60], eR: [47, 62], hR: [44, 67], kL: [40, 84], fL: [37, 94], kR: [53, 84], fR: [55, 94] };
  var TT0 = { H: [59, 47], N: [62, 52], P: [64, 72], eL: [52, 56], hL: [42, 51], eR: [55, 64], hR: [46, 62], kL: [67, 83], fL: [70, 94], kR: [59, 83], fR: [58, 94] };
  var TT1 = { H: [59, 49], N: [62, 54], P: [64, 72], eL: [56, 64], hL: [50, 69], eR: [52, 57], hR: [42, 52], kL: [67, 83], fL: [70, 94], kR: [59, 83], fR: [57, 94] };
  var TT2 = { H: [57, 53], N: [60, 57], P: [65, 74], eL: [54, 62], hL: [45, 66], eR: [58, 62], hR: [54, 70], kL: [68, 84], fL: [71, 94], kR: [60, 84], fR: [57, 94] };
  var TRI = { len: 8.6, you: [[0, TB0], [1.4, TB0], [2.8, TB1], [4.6, TB2], [6.6, TB2], [8.6, TB0]], them: [[0, TT0], [1.4, TT0], [2.8, TT1], [4.6, TT2], [6.6, TT2], [8.6, TT0]] };

  /* calisthenics: one strict muscle-up, dead hang to support and back down */
  var MU = { len: 9, frames: farFill([
    [0, { H: [46, 49], N: [49, 53], P: [49, 72], eL: [49.5, 44], hL: [50, 36], kL: [50, 82], fL: [51, 92] }],
    [1, { H: [46, 49], N: [49, 53], P: [49, 72], eL: [49.5, 44], hL: [50, 36], kL: [50, 82], fL: [51, 92] }],
    [2, { H: [44, 48], N: [47, 51], P: [44, 69], eL: [47, 43], hL: [50, 36], kL: [49, 78], fL: [56, 84] }],
    [3.4, { H: [45, 38], N: [47, 42], P: [46, 60], eL: [41, 40], hL: [50, 36], kL: [51, 68], fL: [55, 76] }],
    [4.4, { H: [57, 32], N: [54, 36], P: [50, 52], eL: [46, 30], hL: [50, 36], kL: [52, 62], fL: [51, 72] }],
    [5.4, { H: [51, 16], N: [50, 21], P: [50, 41], eL: [49, 28], hL: [50, 36], kL: [51, 51], fL: [51, 61] }],
    [6.8, { H: [51, 16], N: [50, 21], P: [50, 41], eL: [49, 28], hL: [50, 36], kL: [51, 51], fL: [51, 61] }],
    [9, { H: [46, 49], N: [49, 53], P: [49, 72], eL: [49.5, 44], hL: [50, 36], kL: [50, 82], fL: [51, 92] }]]) };

  function hookStats(t) { var tt = ((t % HOOK.len) + HOOK.len) % HOOK.len, J = pAt(HOOK.frames, tt); return { knee: pang(J.P, J.kL, J.fL), cm: wallCm(J.P), lock: pang(J.N, J.eR, J.hR) }; }

  /* draw one scene into an svg. o: {ann: labels on, ghost: best-go overlay, trail: hip path} */
  var pTrails = {};
  function pScene(svg, name, t, o) {
    o = o || {}; var s = '', ann = o.ann, vb, key = svg.id || name;
    if (name === 'hook') {
      vb = [12, 2, 62, 76];
      var tt = ((t % HOOK.len) + HOOK.len) % HOOK.len, J0 = pAt(HOOK.frames, tt), J = {};
      for (var k0 in J0) J[k0] = HR(J0[k0]);
      s += '<g transform="rotate(' + HROT + ' 45 50)">' + hookWall(vb[0], vb[0] + vb[2], vb[1], vb[1] + vb[3]) + '</g>';
      if (o.trail) {
        var tr = pTrails[key] = pTrails[key] || []; tr.push(J.P.slice()); if (tr.length > 70) tr.shift();
        s += '<polyline fill="none" stroke="' + PWHITE + '" stroke-opacity=".4" stroke-width=".35" stroke-dasharray=".8 1" points="' + tr.map(function (p) { return f(p[0]) + ',' + f(p[1]); }).join(' ') + '"/>';
      }
      if (o.ghost) {
        var G = {}, n = [.915 * 3, -.4 * 3];
        for (var k in J0) G[k] = HR(/^(hL|hR|fL)$/.test(k) || (k === 'fR' && tt < 4) ? J0[k] : [J0[k][0] + n[0], J0[k][1] + n[1]]);
        s += pfig(G, PWHITE, .4, true);
      }
      s += pfig(J, PBLUE, 1);
      if (ann) {
        s += '<g fill="' + PWHITE + '" font-family="DM Mono, monospace" font-size="1.9">';
        s += parc(J.P, J.kL, J.fL, 3, 0, -1) + parc(J.N, J.eR, J.hR, 2.6, 0, 1);
        var wp = HR([WX(J0.P[1]), J0.P[1]]), d = wallCm(J0.P);
        s += '<line x1="' + f(J.P[0]) + '" y1="' + f(J.P[1]) + '" x2="' + f(wp[0]) + '" y2="' + f(wp[1]) + '" stroke="' + PBLUE + '" stroke-width=".4" stroke-dasharray="1 .8"/><text x="' + f((J.P[0] + wp[0]) / 2 + 1) + '" y="' + f((J.P[1] + wp[1]) / 2 + 3.2) + '" text-anchor="middle">' + Math.round(d) + 'cm</text>';
        if (tt > 2 && tt < 5) s += pPin(J.fL, 7, -8, 'HEEL HOOK', 'PULL THROUGH THE HEEL');
        else if (tt >= 5 && tt < 8.6) s += pPin(J.hL, 8, -3, 'REACH', 'HIPS IN FIRST');
        s += '<text x="' + (vb[0] + 2) + '" y="' + (vb[1] + vb[3] - 2) + '" fill-opacity=".5">35° OVERHANG</text>';
        s += '</g>';
      }
    } else if (name === 'tri') {
      vb = [18, 38, 64, 60];
      var tb = ((t % TRI.len) + TRI.len) % TRI.len, Y = pAt(TRI.you, tb), T = pAt(TRI.them, tb);
      s += '<rect x="-40" y="93.4" width="200" height="40" fill="#101111"/><line x1="-40" y1="93.4" x2="160" y2="93.4" stroke="' + PWHITE + '" stroke-opacity=".35" stroke-width=".35"/>';
      for (var m = -40; m < 160; m += 10) s += '<line x1="' + m + '" y1="93.4" x2="' + (m - 6) + '" y2="100" stroke="#000" stroke-width=".4"/>';
      s += pfig(T, PWHITE, .7);
      s += pfig(Y, PBLUE, 1);
      if (ann) {
        s += '<g fill="' + PWHITE + '" font-family="DM Mono, monospace" font-size="1.9">' + parc(Y.P, Y.kR, Y.fR, 2.6, 0, 1) + parc(Y.H, Y.N, Y.P, 2.6, 0, -1);
        if (tb > .2 && tb < 3) s += pPin(Y.hL, -14, -9, 'COLLAR TIE', 'HEAD UP, ELBOW IN');
        else if (tb >= 3.4 && tb < 7.4) s += pPin(Y.H, 6, -6, 'ARM DRAG', 'HIPS TO THE ANGLE');
        s += '</g>';
      }
    } else {
      vb = [26, 10, 48, 86];
      var tm = ((t % MU.len) + MU.len) % MU.len, M = pAt(MU.frames, tm);
      s += '<line x1="20" y1="36" x2="80" y2="36" stroke="' + PWHITE + '" stroke-opacity=".7" stroke-width="1.1" stroke-linecap="round"/><line x1="26" y1="36" x2="26" y2="0" stroke="' + PWHITE + '" stroke-opacity=".25" stroke-width=".6"/><line x1="74" y1="36" x2="74" y2="0" stroke="' + PWHITE + '" stroke-opacity=".25" stroke-width=".6"/>';
      s += pfig(M, PBLUE, 1);
      if (ann) {
        s += '<g fill="' + PWHITE + '" font-family="DM Mono, monospace" font-size="1.9">' + parc(M.N, M.eL, M.hL, 2.6, 0, -1) + parc(M.N, M.P, M.fL, 3, 0, 1);
        if (tm > 3.6 && tm < 5.2) s += pPin(M.H, 6, -6, 'TRANSITION', 'ELBOWS OVER FAST');
        s += '<text x="76" y="94" text-anchor="end">' + (tm > 5.2 && tm < 8 ? 'REP 1 / STRICT' : 'REP 0') + '</text></g>';
      }
    }
    svg.setAttribute('viewBox', vb.join(' '));
    svg.innerHTML = s;
  }
