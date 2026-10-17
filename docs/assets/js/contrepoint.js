/* =============================================================================
   Contrepoint — affichage des données
   -----------------------------------------------------------------------------
   Lit les fichiers docs/data/*.json produits chaque nuit par le pipeline Python
   et remplit la page. Aucun chiffre n'est calculé ici, à une exception près :
   l'écart cumulé jour par jour du graphique, recalculé à partir des séries
   « base 100 » du pipeline avec la même formule (l'écart en fin de période est
   donc identique à celui du tableau).
   Logique d'affichage reprise de la maquette Claude Design, sans React.
   Règle : aucune animation n'affiche une valeur fausse (pas de compteur qui
   défile, pas de courbe qui se déforme) ; on utilise des fondus.
   ============================================================================= */
'use strict';
(function () {
  const DONNEES = 'data/';
  const C = { encre: '#15171C', papier: '#F5F4F0', vert: '#2A7D4F', rouge: '#C23A2E', vertF: '#1E5E38', rougeF: '#9E2B22', neutre: '#3D4048' };
  const ETIQUETTES = {
    'positif': { label: 'Positif', icone: '▲', bg: '#E2F1E7', fg: '#1E5E38', bd: '#B3D7C0', bs: 'solid', valeur: C.vert, bande: 'rgba(42, 125, 79, 0.26)' },
    'neutre': { label: 'Neutre', icone: '●', bg: '#ECEBE6', fg: '#3D4048', bd: '#D0CEC6', bs: 'solid', valeur: C.neutre, bande: 'rgba(61, 64, 72, 0.18)' },
    'négatif': { label: 'Négatif', icone: '▼', bg: '#F9E3E0', fg: '#9E2B22', bd: '#EDBDB7', bs: 'solid', valeur: C.rouge, bande: 'rgba(194, 58, 46, 0.28)' },
    'signal insuffisant': { label: 'Signal insuffisant', icone: '○', bg: 'transparent', fg: '#3D4048', bd: '#8E8C85', bs: 'dashed' }
  };
  const ETF = {
    msci_world: { label: 'MSCI World', court: 'MSCI World' },
    screened: { label: 'ESG large (Screened)', court: 'Screened' },
    sri: { label: 'ESG strict (SRI)', court: 'SRI' },
    paris: { label: 'Climat (Paris-Aligned)', court: 'Paris-Aligned' },
    bnp_sri_pab: { label: 'BNP Easy SRI PAB', court: 'BNP SRI PAB' }
  };
  const PERIODES = {
    '1m': { kpi: '1 mois', unite: 'jour' }, '3m': { kpi: '3 mois', unite: 'jour' },
    'ytd': { kpi: 'depuis janvier', unite: 'semaine' }, '1a': { kpi: '1 an', unite: 'semaine' },
    '3a': { kpi: '3 ans', unite: 'mois' }, '5a': { kpi: '5 ans', unite: 'mois' }
  };
  const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
  const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  const DEBUT_COLLECTE = '2026-10-16';
  const reduit = (() => { try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } })();

  let D = {};               // données chargées
  const S = { periode: '1a', etf: 'sri', grp: 'marche', tgrp: 'marche', secEtf: 'sri', panneau: null, phase: null, hov: null };
  let G = null;             // graphique courant (séries calculées)
  const $ = (id) => document.getElementById(id);

  /* ---------------------------------------------------------------- Format */
  // Même règle que la maquette : signe + ou − (vrai signe moins), virgule décimale, « 0 » pour zéro.
  function fmt(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    const p = Math.pow(10, d), x = Math.round(v * p) / p;
    if (x === 0) return '0';
    return (x > 0 ? '+' : '−') + Math.abs(x).toFixed(d).replace('.', ',');
  }
  function nb(v, d) { return (v === null || v === undefined || !isFinite(v)) ? '—' : Math.abs(v) === 0 ? (0).toFixed(d).replace('.', ',') : (v < 0 ? '−' : '') + Math.abs(v).toFixed(d).replace('.', ','); }
  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
  function jjmm(iso) { return iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) : ''; }
  function jjmmaaaa(iso) { return iso ? iso.slice(8, 10) + '/' + iso.slice(5, 7) + '/' + iso.slice(0, 4) : ''; }
  function dateLongue(iso) { return iso ? (+iso.slice(8, 10)) + ' ' + MOIS_LONGS[+iso.slice(5, 7) - 1] + ' ' + iso.slice(0, 4) : ''; }
  function parisHorodatage(utc) {
    const d = new Date(utc);
    const f = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', day: '2-digit', month: '2-digit', year: 'numeric', hour: 'numeric', minute: '2-digit' });
    const p = Object.fromEntries(f.formatToParts(d).map((x) => [x.type, x.value]));
    return { date: p.day + '/' + p.month + '/' + p.year, heure: (+p.hour) + ' h ' + p.minute };
  }
  function pluriel(n, mot) { return n + ' ' + mot + (Math.abs(n) >= 2 ? 's' : ''); }
  function couleurSigne(v, fonce) { return v < 0 ? (fonce ? C.rougeF : C.rouge) : (fonce ? C.vertF : C.vert); }

  /* ----------------------------------------------------------- Chargement */
  async function lire(nom) {
    try {
      const r = await fetch(DONNEES + nom + '.json', { cache: 'no-cache' });
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }
  async function charger() {
    const noms = ['performance', 'sentiment', 'secteurs', 'parallele', 'synthese', 'etat', 'methodologie'];
    const res = await Promise.all(noms.map(lire));
    noms.forEach((n, i) => { D[n] = res[i]; });
    if (!D.performance) {
      const e = $('erreur-chargement');
      e.hidden = false;
      e.textContent = 'Les données n’ont pas pu être chargées. Réessayez dans quelques instants.';
      return false;
    }
    if (D.performance.defaut_esg) S.etf = D.performance.defaut_esg;
    return true;
  }

  /* -------------------------------------------------------- État d'écran */
  function etatEcran() {
    const e = D.etat || {}, et = e.etapes || {};
    const heures = e.derniere_execution_utc ? (Date.now() - new Date(e.derniere_execution_utc).getTime()) / 3.6e6 : 0;
    const echecs = ['performance', 'sentiment'].filter((k) => et[k] && et[k].statut === 'echec');
    const retard = heures > 30 || echecs.length > 0;
    const seance = (D.sentiment && D.sentiment.derniere_seance) || D.performance.derniere_seance;
    return {
      retard: retard, echecs: echecs, heures: heures,
      seance: seance,
      suffixe: retard ? ' · ' + jjmm(seance) : '',
      provisoire: !!D.performance.derniere_seance_provisoire
    };
  }

  /* -------------------------------------------------------------- Bandeau */
  function rendreBandeau(E) {
    const e = D.etat || {};
    const h = e.derniere_execution_utc ? parisHorodatage(e.derniere_execution_utc) : null;
    const seance = D.performance.derniere_seance;
    let texte = (h ? 'Mis à jour le ' + h.date + ' à ' + h.heure + ' — ' : '') + 'séance du ' + jjmm(seance);
    if (E.provisoire) texte += ' · dernière clôture provisoire*';
    $('panneau-bandeau').textContent = texte;
    if (E.retard) {
      const r = $('bandeau-retard');
      r.hidden = false;
      const raison = E.echecs.length
        ? 'Le traitement de cette nuit n’a pas pu aboutir (' + E.echecs.map((x) => x === 'performance' ? 'performances' : 'sentiment').join(' et ') + ')'
        : 'Aucune mise à jour depuis ' + Math.floor(E.heures) + ' heures';
      $('bandeau-retard-texte').innerHTML = '<strong style="font-weight: 600; color: #15171C">Dernière mise à jour le ' + esc(h ? h.date + ' à ' + h.heure : '—') +
        ' — séance du ' + esc(jjmm(seance)) + '.</strong> ' + esc(raison) + ' : les chiffres affichés sont les derniers disponibles. Prochaine mise à jour prévue la nuit prochaine.';
    } else {
      $('bandeau').hidden = false;
      $('bandeau-texte').textContent = texte;
    }
  }

  /* ------------------------------------------------------ Cartes d'humeur */
  function tagHtml(etiquette) {
    const t = ETIQUETTES[etiquette] || ETIQUETTES['neutre'];
    return '<span class="tag" style="background: ' + t.bg + '; color: ' + t.fg + '; border: 1px ' + t.bs + ' ' + t.bd + '"><span aria-hidden="true" style="font-size: ' + (t.icone === '○' ? '10' : '9') + 'px">' + t.icone + '</span>' + t.label + '</span>';
  }
  function jauge(solde, marge, etiquette) {
    const t = ETIQUETTES[etiquette] || ETIQUETTES['neutre'];
    const lo = Math.max(-50, solde - marge), hi = Math.min(50, solde + marge);
    const pos = Math.max(-50, Math.min(50, solde));
    return '<div style="display: flex; flex-direction: column; gap: 6px">' +
      '<div style="position: relative; height: 14px">' +
      '<div style="position: absolute; left: 0; right: 0; top: 6px; height: 2px; background: linear-gradient(90deg, rgba(194, 58, 46, 0.5) 0 50%, rgba(42, 125, 79, 0.5) 50% 100%)"></div>' +
      '<div style="position: absolute; left: 50%; top: 0; width: 1px; height: 14px; background: #9A9890"></div>' +
      '<div style="position: absolute; left: ' + (lo + 50).toFixed(1) + '%; width: ' + Math.max(0, hi - lo).toFixed(1) + '%; top: 4px; height: 6px; border-radius: 3px; background: ' + t.bande + '"></div>' +
      '<div style="position: absolute; left: ' + (pos + 50).toFixed(1) + '%; top: 1px; width: 12px; height: 12px; margin-left: -6px; border-radius: 50%; background: ' + t.valeur + '; border: 2px solid #F5F4F0; box-sizing: border-box"></div>' +
      '</div>' +
      '<div class="num" style="display: flex; justify-content: space-between; font-size: 12px; color: #5C6068"><span style="color: #9E2B22">−50</span><span>0</span><span style="color: #1E5E38">+50</span></div></div>';
  }
  function ligneCouverture(g) {
    const r = g.releves_reussis, a = g.releves_attendus;
    const aide = 'Une journée est complète si au moins 75 % des relevés prévus (un toutes les 3 heures) ont réussi, dont un après la clôture, sans trou de plus de 12 heures. Ici, le plus long trou a duré ' +
      nb(g.plus_long_trou_heures, 1) + ' h. Le solde reste affiché, mais cette journée est exclue des tests statistiques.';
    return '<p class="num" style="margin: 0; display: flex; align-items: center; gap: 7px; font-size: 13px; color: #4A4E57">' +
      '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="none" stroke="#4A4E57" stroke-width="1.2"></circle><path d="M6 1a5 5 0 0 1 0 10z" fill="#4A4E57"></path></svg>' +
      '<span>Couverture partielle : ' + r + ' relevé' + (r >= 2 ? 's' : '') + ' réussi' + (r >= 2 ? 's' : '') + ' sur ' + a + ' attendus</span>' +
      '<button type="button" class="tip tipl bouton-aide" aria-label="En savoir plus sur la couverture partielle">?<span class="tipbox" role="tooltip">' + esc(aide) + '</span></button></p>';
  }
  function rendreCarte(id, groupe, nom, E) {
    const el = $(id);
    const g = D.sentiment && D.sentiment.groupes ? D.sentiment.groupes[groupe] : null;
    const titre = '<h2 class="kicker">Humeur ' + nom + esc(E.suffixe) + '</h2>';
    if (!g) {
      el.innerHTML = '<div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">' + titre + '</div>' +
        '<p style="margin: 0; font-size: 14px; color: #4A4E57">Pas encore de journée de sentiment close.</p>';
      return;
    }
    const entete = '<div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">' + titre + tagHtml(g.etiquette) + '</div>';
    if (g.etiquette === 'signal insuffisant') {
      // Deux cas possibles : moins de 30 articles, ou marge d'erreur supérieure à 25 points.
      const n = g.nb_articles, peu = n < 30;
      const segs = [];
      for (let i = 0; i < 30; i++) segs.push('<span style="display: block; height: 14px; box-sizing: border-box; background: ' + (i < n ? '#4A4E57' : 'transparent') + '; border: 1px solid ' + (i < n ? '#4A4E57' : '#9A9890') + '"></span>');
      const detail = peu
        ? 'Ici, seulement ' + n + ' article' + (n >= 2 ? 's' : '') + '.'
        : 'Ici, ' + n + ' articles, mais une marge d’erreur de ± ' + nb(g.marge_erreur, 1) + ' points.';
      el.innerHTML = entete +
        '<div style="display: flex; align-items: baseline; gap: 12px"><span class="num chiffre">' + n + '</span>' +
        '<span class="num" style="font-size: 15px; color: #4A4E57">' + (peu ? 'articles sur 30 requis' : 'articles · marge ± ' + nb(g.marge_erreur, 1)) + '</span></div>' +
        '<div style="display: flex; flex-direction: column; gap: 6px">' +
        '<div role="img" aria-label="' + n + ' articles collectés sur 30 requis" style="display: grid; grid-template-columns: repeat(30, minmax(0, 1fr)); gap: 3px; height: 14px">' + segs.join('') + '</div>' +
        '<div class="num" style="display: flex; justify-content: space-between; font-size: 12px; color: #5C6068"><span>0</span><span>seuil de publication : 30 articles et marge ≤ 25 points</span></div></div>' +
        '<p style="margin: 0; font-size: 13px; line-height: 1.5; color: #4A4E57">Pas de solde publiable pour cette journée : il faut au moins 30 articles et une marge d’erreur d’au plus 25 points. ' + esc(detail) + '</p>' +
        (g.couverture_partielle ? ligneCouverture(g) : '');
      return;
    }
    const t = ETIQUETTES[g.etiquette] || ETIQUETTES['neutre'];
    el.innerHTML = entete +
      '<div style="display: flex; align-items: baseline; gap: 14px">' +
      '<span class="num chiffre" aria-label="Solde ' + esc(fmt(g.solde, 1)) + '" style="color: ' + t.valeur + '">' + fmt(g.solde, 1) + '</span>' +
      '<span class="num" style="font-size: 15px; color: #4A4E57">marge ± ' + nb(g.marge_erreur, 1) + '</span></div>' +
      jauge(g.solde, g.marge_erreur, g.etiquette) +
      '<div style="display: flex; flex-direction: column; gap: 6px">' +
      '<p class="num" style="margin: 0; font-size: 13px; color: #5C6068">Solde de sentiment sur ' + g.nb_articles + ' articles · journée du ' + jjmm(D.sentiment.derniere_seance) + '</p>' +
      (g.couverture_partielle ? ligneCouverture(g) : '') + '</div>';
  }

  /* --------------------------------------------- Carte « Écart ESG strict » */
  function periode(pid) { return (D.performance.periodes || []).find((p) => p.id === pid); }
  function rendreCarteEcart(E) {
    const p = periode(S.periode), info = PERIODES[S.periode];
    $('kx-periode').textContent = info.kpi;
    document.querySelectorAll('.kx-p').forEach((x) => { x.textContent = info.kpi; });
    document.querySelector('#carte-ecart .suffixe-date').textContent = E.suffixe;
    if (!p || !p.disponible) {
      $('kx-valeur').textContent = '—'; $('kx-unite').textContent = 'point'; $('kx-sri').textContent = '—'; $('kx-msci').textContent = '—';
      return;
    }
    const rel = p.etf.sri.perf_relative_pts, sri = p.etf.sri.perf_cumulee_pct, msci = p.etf.msci_world.perf_cumulee_pct;
    const v = $('kx-valeur');
    v.textContent = fmt(rel, 2); v.style.color = couleurSigne(rel); v.setAttribute('aria-label', 'Écart ' + fmt(rel, 2) + ' point');
    $('kx-unite').textContent = Math.abs(rel) >= 2 ? 'points' : 'point';
    const ks = $('kx-sri'); ks.textContent = fmt(sri, 2) + ' %'; ks.style.color = couleurSigne(sri, true);
    const km = $('kx-msci'); km.textContent = fmt(msci, 2) + ' %'; km.style.color = couleurSigne(msci, true);
  }

  /* -------------------------------------------------------------- Synthèse */
  // Texte produit par le module de synthèse du pipeline (règles fixes). Ici, on ne fait que colorer
  // l'étiquette du jour et le verbe de performance, sans modifier un seul mot.
  function rendreSynthese(E) {
    $('synthese-kicker').textContent = E.retard ? 'L’essentiel du ' + jjmm(E.seance) : 'L’essentiel du jour';
    const sy = D.synthese && D.synthese.par_etf ? (D.synthese.par_etf[S.etf] || D.synthese.par_etf[D.synthese.defaut]) : null;
    if (!sy || !sy.length) { $('synthese-texte').textContent = 'Synthèse indisponible.'; return; }
    let h = esc(sy.join(' '));
    h = h.replace(/(Humeur du marché|Actualité ESG)( : )(positive|négative|neutre)/g, (m, a, b, c) => {
      const col = c === 'positive' ? C.vert : c === 'négative' ? C.rouge : C.neutre;
      return a + b + '<span style="color: ' + col + '">' + c + '</span>';
    });
    h = h.replace(/(sous-performe le MSCI World de [\d,]+ points?)/g, '<span style="color: ' + C.rouge + '">$1</span>');
    h = h.replace(/(surperforme le MSCI World de [\d,]+ points?)/g, '<span style="color: ' + C.vert + '">$1</span>');
    const el = $('synthese-texte');
    el.innerHTML = h;
    // Synthèse longue (plusieurs phrases du module) : corps réduit pour garder la vue d'ensemble légère.
    el.classList.toggle('synthese-longue', sy.join(' ').length > 260);
  }

  /* ------------------------------------------------- Graphique principal */
  function pas(etendue) {
    const brut = etendue / 4, mag = Math.pow(10, Math.floor(Math.log10(brut))), f = brut / mag;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
  }
  function domaine(v) {
    let lo = Math.min(0, Math.min.apply(null, v)), hi = Math.max(0, Math.max.apply(null, v));
    const pad = Math.max((hi - lo) * 0.08, 0.05);
    lo -= pad; hi += pad;
    const st = pas(hi - lo);
    return { lo: Math.floor(lo / st) * st, hi: Math.ceil(hi / st) * st };
  }
  function graduations(lo, hi) {
    const st = pas(hi - lo), dec = st >= 1 ? 0 : (st >= 0.1 ? 1 : 2), out = [];
    const k0 = Math.ceil(lo / st - 1e-6), k1 = Math.floor(hi / st + 1e-6);
    for (let k = k1; k >= k0; k--) {
      const t = Math.round(k * st * 1e6) / 1e6;
      out.push({ label: fmt(t, dec), top: ((hi - t) / (hi - lo) * 100).toFixed(3) + '%', couleur: t === 0 ? '#8E8C85' : '#E2E0DA' });
    }
    return out;
  }
  function cleSemaine(iso) {
    const d = new Date(iso + 'T00:00:00Z'), j = (d.getUTCDay() + 6) % 7;
    d.setUTCDate(d.getUTCDate() - j);
    return d.toISOString().slice(0, 10);
  }
  function calculerGraphique() {
    const P = D.performance, p = periode(S.periode), dates = P.series.dates;
    if (!p || !p.disponible) return null;
    let i0 = dates.indexOf(p.debut), i1 = dates.indexOf(p.fin);
    if (i0 < 0) i0 = dates.findIndex((d) => d >= p.debut);
    if (i1 < 0) i1 = dates.length - 1;
    const be = P.series.base100[S.etf], br = P.series.base100[P.reference];
    if (!be || !br) return null;
    const ds = dates.slice(i0, i1 + 1);
    // Écart cumulé en points = performance cumulée de l'ETF − performance cumulée du MSCI World depuis le début de la période.
    const v = ds.map((_, k) => (be[i0 + k] / be[i0] - br[i0 + k] / br[i0]) * 100);
    const unite = PERIODES[S.periode].unite;
    const histo = ((D.sentiment && D.sentiment.historique) || []).filter((h) => h.groupe === S.grp);
    const parJour = {}; histo.forEach((h) => { parJour[h.seance] = h; });
    let seaux = [];
    if (unite === 'jour') {
      ds.forEach((d, k) => { if (parJour[d]) seaux.push({ k: k, h: parJour[d], type: 'jour' }); });
    } else {
      const ag = (D.sentiment && D.sentiment.agregats && D.sentiment.agregats[S.grp] && D.sentiment.agregats[S.grp][unite]) || [];
      ag.forEach((a) => {
        if (a.derniere_seance < ds[0] || a.debut > ds[ds.length - 1]) return;
        let k = ds.indexOf(a.derniere_seance);
        if (k < 0) k = ds.findIndex((d) => d >= a.derniere_seance);
        if (k < 0) k = ds.length - 1;
        seaux.push({ k: k, a: a, type: unite });
      });
    }
    const cles = new Set(ds.map((d) => unite === 'jour' ? d : unite === 'semaine' ? cleSemaine(d) : d.slice(0, 7)));
    return { p: p, ds: ds, v: v, dom: domaine(v), unite: unite, seaux: seaux, nbSeaux: cles.size, parJour: parJour };
  }
  function rect(x, w, v, z) {
    const h = Math.max(0.8, Math.abs(v) / 50 * z);
    return 'M' + x.toFixed(1) + ' ' + (v >= 0 ? z - h : z).toFixed(1) + 'h' + w.toFixed(1) + 'v' + h.toFixed(1) + 'h' + (-w).toFixed(1) + 'Z';
  }
  function rendreGraphique(E) {
    G = calculerGraphique();
    const e = ETF[S.etf];
    $('g-etf-label').textContent = e.label;
    document.querySelectorAll('.g-etf-court').forEach((x) => { x.textContent = e.court; });
    const grpLabel = S.grp === 'esg' ? 'ESG' : 'Marché';
    if (!G) { $('g-sous-titre').textContent = 'Période indisponible.'; return; }
    const unitLabel = G.unite === 'jour' ? 'quotidien' : (G.unite === 'semaine' ? 'moyenne hebdomadaire' : 'moyenne mensuelle');
    $('g-sous-titre').textContent = 'Écart de performance cumulé, en points · solde de sentiment ' + grpLabel + ', ' + unitLabel + (E.retard ? ' · jusqu’au ' + jjmm(G.ds[G.ds.length - 1]) : '');
    const { lo, hi } = G.dom, H = 260, n = G.v.length;
    const Y = (x) => (hi - x) / (hi - lo) * H;
    const chemin = G.v.map((x, i) => (i ? 'L' : 'M') + (n > 1 ? i / (n - 1) * 1000 : 0).toFixed(1) + ' ' + Y(x).toFixed(1)).join('');
    $('g-courbe').setAttribute('d', chemin);
    $('g-aire').setAttribute('d', chemin + 'L1000 ' + Y(0).toFixed(1) + 'L0 ' + Y(0).toFixed(1) + 'Z');
    $('g-point-fin').style.top = (8 + Y(G.v[n - 1])).toFixed(1) + 'px';
    const tk = graduations(lo, hi);
    $('g-grille').innerHTML = tk.map((t) => '<div style="position: absolute; left: 0; right: 0; top: ' + t.top + '; height: 1px; background: ' + t.couleur + '"></div>').join('');
    $('g-axe').innerHTML = tk.map((t) => '<span class="num" style="position: absolute; left: 0; top: ' + t.top + '; transform: translateY(-50%); font-size: 12px; color: #5C6068">' + t.label + '</span>').join('');
    // Dates en abscisse.
    $('g-dates').innerHTML = [0, 0.25, 0.5, 0.75, 1].map((f, k) => {
      const d = G.ds[Math.round(f * (n - 1))];
      const lab = G.unite === 'jour' ? (+d.slice(8, 10)) + ' ' + MOIS[+d.slice(5, 7) - 1] : MOIS[+d.slice(5, 7) - 1] + ' ' + d.slice(0, 4);
      return '<span class="num" style="position: absolute; top: 0; left: ' + (f * 100) + '%; transform: translateX(' + (k === 0 ? '0' : (k === 4 ? '-100%' : '-50%')) + '); white-space: nowrap">' + lab + '</span>';
    }).join('');
    // Barres de sentiment.
    const z = 48;
    let pos = '', neg = '', ppos = '', pneg = '', partielle = false;
    const bwJour = 1000 / n;
    G.seaux.forEach((s) => {
      let v, part = false;
      if (s.type === 'jour') {
        if (s.h.etiquette === 'signal insuffisant') return;
        v = s.h.solde; part = String(s.h.couverture_partielle) === 'true' || s.h.couverture_partielle === true;
      } else {
        if (s.a.solde_moyen === null) return;
        v = s.a.solde_moyen;
      }
      const bw = s.type === 'jour' ? bwJour : 1000 / G.nbSeaux;
      const w = Math.max(1.5, bw * 0.62), centre = (s.k + 0.5) * bwJour;
      const x = Math.min(1000 - w, Math.max(0, centre - w / 2));
      const seg = rect(x, w, v, z);
      if (part) { partielle = true; if (v >= 0) ppos += seg; else pneg += seg; } else if (v >= 0) pos += seg; else neg += seg;
    });
    $('b-pos').setAttribute('d', pos || 'M0 0'); $('b-neg').setAttribute('d', neg || 'M0 0');
    $('b-part-pos').setAttribute('d', ppos || 'M0 0'); $('b-part-neg').setAttribute('d', pneg || 'M0 0');
    $('legende-partielle').hidden = !partielle;
    const debut = $('b-debut-collecte');
    debut.hidden = !(G.ds[0] < DEBUT_COLLECTE);
    const auMoinsUne = !!(pos || neg || ppos || pneg);
    debut.textContent = 'Collecte du sentiment démarrée le 16/10/2026' + (!auMoinsUne && G.unite !== 'jour'
      ? ' · aucune ' + (G.unite === 'semaine' ? 'semaine' : 'période mensuelle') + ' avec une journée complète pour l’instant' : '');
    const dernier = G.parJour[G.ds[G.ds.length - 1]];
    const trou = $('b-trou');
    trou.hidden = !(G.unite === 'jour' && dernier && dernier.etiquette === 'signal insuffisant');
    if (!trou.hidden) trou.textContent = jjmm(dernier.seance) + ' : signal insuffisant, pas de barre';
    $('g-ecart-fin').textContent = fmt(G.v[n - 1], 2) + ' pt';
    $('plot').setAttribute('aria-label', 'Graphique : écart cumulé ' + e.court + ' − MSCI World et solde de sentiment ' + grpLabel + '. Flèches gauche et droite pour parcourir les dates.');
    masquerInfobulle();
  }

  /* -------------------------------------------- Infobulle du graphique */
  function soldeA(k) {
    const d = G.ds[k];
    const grp = S.grp === 'esg' ? 'ESG' : 'Marché';
    const label = 'Solde ' + grp + (G.unite === 'jour' ? ' du jour' : (G.unite === 'semaine' ? ', moy. hebdo.' : ', moy. mensuelle'));
    if (d < DEBUT_COLLECTE) return { label: label, texte: 'collecte non démarrée', note: '' };
    if (G.unite === 'jour') {
      const h = G.parJour[d];
      if (!h) return { label: label, texte: 'pas de donnée', note: '' };
      if (h.etiquette === 'signal insuffisant') return { label: label, texte: 'signal insuffisant', note: h.nb_articles + ' articles' };
      const part = String(h.couverture_partielle) === 'true' || h.couverture_partielle === true;
      return { label: label, v: h.solde, texte: fmt(h.solde, 1), note: (ETIQUETTES[h.etiquette] || {}).label + ' · ' + h.nb_articles + ' articles' + (part ? ' · journée partielle' : '') };
    }
    const cle = G.unite === 'semaine' ? cleSemaine(d) : d.slice(0, 7);
    const ag = ((D.sentiment.agregats || {})[S.grp] || {})[G.unite] || [];
    const a = ag.find((x) => (G.unite === 'semaine' ? x.debut === cle : x.debut.slice(0, 7) === cle));
    if (!a) return { label: label, texte: 'pas de donnée', note: '' };
    const note = pluriel(a.nb_jours, 'journée') + ' retenue' + (a.nb_jours >= 2 ? 's' : '') + ', ' + a.nb_jours_ecartes + ' écartée' + (a.nb_jours_ecartes >= 2 ? 's' : '');
    if (a.solde_moyen === null) return { label: label, texte: 'aucune journée complète', note: note };
    return { label: label, v: a.solde_moyen, texte: fmt(a.solde_moyen, 1), note: note };
  }
  function montrerInfobulle(f, y, w) {
    if (!G) return;
    const n = G.v.length, k = Math.round(Math.max(0, Math.min(1, f)) * (n - 1));
    S.hov = { k: k, w: w };
    const gx = (n > 1 ? k / (n - 1) : 0) * w, val = G.v[k];
    const { lo, hi } = G.dom, dy = (hi - val) / (hi - lo) * 260;
    const so = soldeA(k), d = G.ds[k];
    $('tt-date').textContent = (+d.slice(8, 10)) + ' ' + MOIS[+d.slice(5, 7) - 1] + ' ' + d.slice(0, 4);
    const ec = $('tt-ecart'); ec.textContent = fmt(val, 2) + ' pt'; ec.style.color = val < 0 ? '#FF9C92' : '#8BE3B4';
    $('tt-solde-label').textContent = so.label;
    const sv = $('tt-solde'); sv.textContent = so.texte; sv.style.color = so.v === undefined ? '#C9C7C0' : (so.v < 0 ? '#FF9C92' : '#8BE3B4');
    const note = $('tt-note'); note.textContent = so.note; note.style.display = so.note ? 'block' : 'none';
    const boite = $('tt-boite'), bw = 232, bh = boite.offsetHeight || 92;
    let bx = gx + 16; if (bx + bw > w) bx = gx - 16 - bw;
    const yy = y == null ? dy : y;
    const by = Math.max(0, Math.min(370 - bh, yy - bh / 2));
    $('tt-ligne').style.transform = 'translateX(' + gx.toFixed(1) + 'px)';
    $('tt-point').style.transform = 'translate(' + gx.toFixed(1) + 'px, ' + dy.toFixed(1) + 'px)';
    boite.style.transform = 'translate(' + bx.toFixed(1) + 'px, ' + by.toFixed(1) + 'px)';
    ['tt-ligne', 'tt-point', 'tt-boite'].forEach((id) => { $(id).style.opacity = '1'; });
    $('tt-annonce').textContent = $('tt-date').textContent + ' : écart ' + ec.textContent + ', ' + so.label.toLowerCase() + ' ' + so.texte + '.';
  }
  function masquerInfobulle() {
    ['tt-ligne', 'tt-point', 'tt-boite'].forEach((id) => { const x = $(id); if (x) x.style.opacity = '0'; });
    if (S.hov) S.hov.on = false;
  }
  function brancherGraphique() {
    const plot = $('plot');
    let attente = 0, dernier = null;
    plot.addEventListener('mousemove', (ev) => {
      const r = plot.getBoundingClientRect();
      dernier = { f: (ev.clientX - r.left) / r.width, y: ev.clientY - r.top, w: r.width };
      // Une seule mise à jour par image, comme dans la maquette.
      if (!attente) attente = requestAnimationFrame(() => { attente = 0; montrerInfobulle(dernier.f, dernier.y, dernier.w); });
    });
    plot.addEventListener('mouseleave', () => { if (attente) { cancelAnimationFrame(attente); attente = 0; } masquerInfobulle(); });
    plot.addEventListener('focus', () => montrerInfobulle(1, null, plot.getBoundingClientRect().width));
    plot.addEventListener('blur', masquerInfobulle);
    plot.addEventListener('keydown', (ev) => {
      if (!G) return;
      const n = G.v.length, w = plot.getBoundingClientRect().width;
      let k = S.hov && S.hov.k !== undefined ? S.hov.k : n - 1;
      if (ev.key === 'ArrowLeft') k = Math.max(0, k - 1);
      else if (ev.key === 'ArrowRight') k = Math.min(n - 1, k + 1);
      else if (ev.key === 'Home') k = 0;
      else if (ev.key === 'End') k = n - 1;
      else if (ev.key === 'Escape') { masquerInfobulle(); return; }
      else return;
      ev.preventDefault();
      montrerInfobulle(n > 1 ? k / (n - 1) : 0, null, w);
    });
  }

  /* ------------------------------------------------ Tableau des performances */
  function alerte(id, texte) {
    return '<button type="button" class="tip" aria-label="Fiabilité réduite" aria-describedby="' + id + '" style="display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; padding: 0; border: 1px solid #DBA49E; border-radius: 50%; background: #F9E3E0; color: #9E2B22; font-size: 12px; cursor: help">⚠︎<span class="tipbox" id="' + id + '" role="tooltip">' + esc(texte) + '</span></button>';
  }
  function rendreTableau(E) {
    $('table-prefixe').textContent = E.retard ? 'Au ' + jjmm(D.performance.derniere_seance) + ' · ' : '';
    const per = { '1a': periode('1a'), '3a': periode('3a'), '5a': periode('5a') };
    const val = (pid, id) => (per[pid] && per[pid].disponible ? per[pid].etf[id] : null);
    const AIDE = 'Fiabilité réduite : sur cette période, une partie de l’historique vient d’une cotation peu échangée (Amsterdam, en dollars, convertie en euros). Volatilité, écart de suivi et Sharpe sont à lire avec prudence. Détails dans la méthodologie.';
    const ligne = (id, opts) => {
      const ref = id === D.performance.reference;
      const cell = (pid) => {
        const v = val(pid, id);
        if (!v) return '—';
        return ref ? fmt(v.perf_cumulee_pct, 2) + ' %' : fmt(v.perf_relative_pts, 2) + ' pt';
      };
      const v5 = val('5a', id), v1 = val('1a', id);
      const sharpe = v5 && v5.sharpe !== null ? nb(v5.sharpe, 2) : '—';
      const sharpeHtml = v5 && v5.risque_fiabilite_reduite ? '<span style="display: inline-flex; align-items: center; gap: 6px">' + sharpe + alerte('tip-' + id + '-5a', AIDE) + '</span>' : sharpe;
      const te = ref ? '<span style="color: #5C6068">—</span>' : (v1 && v1.ecart_suivi_pct !== undefined ? nb(v1.ecart_suivi_pct, 1) + ' %' : '—');
      const teHtml = !ref && v1 && v1.risque_fiabilite_reduite ? '<span style="display: inline-flex; align-items: center; gap: 6px">' + te + alerte('tip-' + id + '-1a', AIDE) + '</span>' : te;
      const nom = ref ? 'MSCI World <span style="font-weight: 400; color: #5C6068">(référence)</span>' : esc(ETF[id].label);
      const poids = ref ? ' style="font-weight: 600"' : '';
      return '<tr style="' + (opts.complement ? 'color: #4A4E57; font-style: italic' : 'border-bottom: 1px solid #D8D6CF') + (opts.surligne ? '; background: rgba(21, 23, 28, 0.035)' : '') + '">' +
        '<th scope="row" style="font-weight: ' + (ref ? 600 : (opts.complement ? 400 : 500)) + '">' + nom + '</th>' +
        '<td' + poids + '>' + cell('1a') + '</td><td' + poids + '>' + cell('3a') + '</td><td' + poids + '>' + cell('5a') + '</td>' +
        '<td>' + sharpeHtml + '</td><td>' + teHtml + '</td></tr>';
    };
    $('table-perf').innerHTML = ligne('msci_world', {}) + ligne('screened', {}) + ligne('sri', { surligne: true }) + ligne('paris', {}) +
      '<tr><td colspan="6" style="text-align: left; padding: 22px 0 8px; font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #5C6068; border-bottom: 1px dashed #B4B2AB">Complément</td></tr>' +
      ligne('bnp_sri_pab', { complement: true });
  }

  /* ------------------------------------ Volet 3 : progression ou résultats */
  function rendreVolet3() {
    const P = D.parallele, tp = P && P.test_principal;
    const bas = $('bas'), aside = $('progression'), section = $('analyse');
    if (!tp) { aside.hidden = true; section.hidden = true; return; }
    if (!(tp.resultat && tp.resultat.disponible)) {
      const pr = tp.progression || { jours_exploitables: 0, jours_requis: 60 };
      const n = pr.jours_exploitables, total = pr.jours_requis;
      aside.hidden = false; section.hidden = true; bas.classList.remove('pleine-largeur');
      aside.innerHTML = '<h2 class="kicker">Analyse en cours de constitution</h2>' +
        '<div style="display: flex; align-items: baseline; gap: 8px"><span class="num" style="font-family: \'Newsreader\', Georgia, serif; font-size: 48px; line-height: 1; font-weight: 500">' + n + '</span>' +
        '<span class="num" style="font-size: 16px; color: #4A4E57">/ ' + total + ' jours de bourse exploitables</span></div>' +
        '<div role="progressbar" aria-label="Jours de bourse exploitables" aria-valuemin="0" aria-valuemax="' + total + '" aria-valuenow="' + n + '" style="height: 6px; background: #E2E0DA; border-radius: 3px; overflow: hidden">' +
        '<div class="fade-remplissage" style="width: ' + Math.min(100, n / total * 100).toFixed(2) + '%; height: 100%; background: #15171C"></div></div>' +
        '<p style="margin: 0; font-size: 14px; line-height: 1.5; color: #4A4E57">Premiers résultats estimés : <strong style="color: #15171C">' + (pr.date_estimee ? 'vers le ' + dateLongue(pr.date_estimee) : '—') + '</strong></p>' +
        '<p style="margin: 0; font-size: 12px; line-height: 1.5; color: #5C6068">Une journée est exploitable si son signal est suffisant et ses relevés complets. Estimation calculée sur le calendrier de la Bourse de Francfort, ' + esc(pr.hypothese || '') + '.</p>';
      return;
    }
    aside.hidden = true; section.hidden = false; bas.classList.add('pleine-largeur');
    rendreAnalyse(P, tp);
  }
  function rendreAnalyse(P, tp) {
    const bloc = P.etf.sri.marche, t = tp.resultat, n = t.n;
    const zone = P.zone_hasard_correlation_glissante || { seuil: 0.361, fenetre: 30 };
    const s = zone.seuil;
    // 1. Test principal.
    const verdict = t.significatif ? (t.sens === 'positif' ? 'Lien positif détecté' : 'Lien négatif détecté') : 'Pas d’effet détectable';
    const colPrincipal = '<article style="display: flex; flex-direction: column; gap: 14px; padding: 22px 36px 8px 0; border-right: 1px solid #D8D6CF">' +
      '<h3 class="kicker">Test principal · Le sentiment de J annonce-t-il J+1 ?</h3>' +
      '<p style="margin: 0; font-family: \'Newsreader\', Georgia, serif; font-size: 34px; line-height: 1.15; font-weight: 500">' + verdict + '</p>' +
      '<dl class="num" style="margin: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; row-gap: 8px; column-gap: 16px; padding-top: 12px; border-top: 1px solid #E2E0DA; font-size: 14px">' +
      '<dt style="color: #4A4E57">Corrélation (r)</dt><dd style="margin: 0; text-align: right; font-weight: 600">' + fmt(t.r, 2) + '</dd>' +
      '<dt style="color: #4A4E57">p-valeur</dt><dd style="margin: 0; text-align: right; font-weight: 600">' + nb(t.p, 2) + '</dd>' +
      '<dt style="color: #4A4E57">Observations</dt><dd style="margin: 0; text-align: right; font-weight: 600">' + n + ' paires de jours</dd></dl>' +
      '<p style="margin: 0; font-size: 13px; line-height: 1.5; color: #4A4E57">Seul test fixé à l’avance (le 17/10/2026) : sentiment Marché du jour J et écart de l’ETF SRI face au MSCI World à la séance suivante. ' +
      (t.significatif ? 'Corrélation n’est pas causalité.' : 'Un résultat non significatif ne prouve pas l’absence de lien : seul un effet marqué serait détectable sur cet échantillon.') + '</p></article>';
    // 2. Corrélation glissante (exploratoire), avec la zone du hasard toujours visible.
    const gl = bloc.correlation_glissante || [];
    const yr = (r) => ((0.8 - Math.max(-0.8, Math.min(0.8, r))) / 1.6);
    const chemin = gl.map((x, i) => (i ? 'L' : 'M') + (gl.length > 1 ? i / (gl.length - 1) * 1000 : 0).toFixed(1) + ' ' + (yr(x.r) * 140).toFixed(1)).join('') || 'M0 0';
    const derniere = gl.length ? gl[gl.length - 1].r : null;
    const dansZone = derniere !== null && Math.abs(derniere) < s;
    const colGlissante = '<article style="display: flex; flex-direction: column; gap: 14px; padding: 22px 36px 8px">' +
      '<h3 class="kicker">Exploratoire · Corrélation glissante sur ' + zone.fenetre + ' jours</h3>' +
      '<p class="num" style="margin: 0; display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap"><span style="font-family: \'Newsreader\', Georgia, serif; font-size: 48px; line-height: 1; font-weight: 500">' + (derniere === null ? '—' : fmt(derniere, 2)) + '</span>' +
      '<span style="font-size: 14px; color: #4A4E57">' + (derniere === null ? 'pas encore calculable' : (dansZone ? 'dans la zone du hasard' : 'hors de la zone du hasard')) + '</span></p>' +
      '<div style="display: grid; grid-template-columns: 36px minmax(0, 1fr); column-gap: 10px; row-gap: 6px">' +
      '<div class="num" style="position: relative; height: 140px; font-size: 12px; color: #5C6068"><span style="position: absolute; right: 0; top: 0; transform: translateY(-50%)">+0,8</span><span style="position: absolute; right: 0; top: 50%; transform: translateY(-50%)">0</span><span style="position: absolute; right: 0; top: 100%; transform: translateY(-50%)">−0,8</span></div>' +
      '<div style="position: relative; height: 140px"><div class="rvo" style="position: absolute; top: -8px; bottom: -8px; left: 0; right: -8px"><div class="rvi" style="position: absolute; inset: 0"><div style="position: absolute; top: 8px; left: 0; right: 8px; bottom: 8px">' +
      '<div style="position: absolute; left: 0; right: 0; top: ' + (yr(s) * 100).toFixed(1) + '%; height: ' + ((yr(-s) - yr(s)) * 100).toFixed(1) + '%; background: rgba(21, 23, 28, 0.1)"></div>' +
      '<div style="position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: #8E8C85"></div>' +
      '<svg viewBox="0 0 1000 140" preserveAspectRatio="none" aria-hidden="true" style="position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible"><path d="' + chemin + '" fill="none" stroke="#15171C" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"></path></svg>' +
      (derniere !== null ? '<div style="position: absolute; right: -7px; top: ' + (yr(derniere) * 100).toFixed(2) + '%; width: 9px; height: 9px; margin-top: -6.5px; border-radius: 50%; background: #15171C; border: 2px solid #F5F4F0"></div>' : '') +
      '</div></div></div></div><div></div>' +
      '<div class="num" style="display: flex; justify-content: space-between; font-size: 12px; color: #5C6068"><span>' + (gl.length ? jjmmaaaa(gl[0].seance) : '') + '</span><span>' + (gl.length ? jjmmaaaa(gl[gl.length - 1].seance) : '') + '</span></div></div>' +
      '<p style="margin: 0; display: flex; align-items: center; gap: 8px; font-size: 12px; color: #5C6068"><span aria-hidden="true" style="width: 14px; height: 10px; background: rgba(21, 23, 28, 0.1); flex: none"></span>Zone du hasard au seuil de 5 % (|r| inférieur à ' + nb(s, 2) + ' sur ' + zone.fenetre + ' séances) : à l’intérieur, la courbe ne dit rien.</p></article>';
    // 3. Comparaison des jours (exploratoire), p-valeur corrigée (Holm).
    const jours = bloc.journees || [];
    const moyenne = (lab) => { const v = jours.filter((j) => j.etiquette === lab && j.relatif_j_pts !== null).map((j) => j.relatif_j_pts); return { n: v.length, m: v.length ? v.reduce((a, b) => a + b, 0) / v.length : null }; };
    const pos = moyenne('positif'), neu = moyenne('neutre'), neg = moyenne('négatif');
    const histo = ((D.sentiment && D.sentiment.historique) || []).filter((h) => h.groupe === 'marche' && h.seance >= DEBUT_COLLECTE);
    const exclusInsuf = histo.filter((h) => h.etiquette === 'signal insuffisant').length;
    const exclusPart = histo.filter((h) => h.etiquette !== 'signal insuffisant' && (String(h.couverture_partielle) === 'true' || h.couverture_partielle === true)).length;
    const ligneT = (icone, couleur, lab, o) => '<tr style="border-bottom: 1px solid #E2E0DA"><th scope="row" style="text-align: left; padding: 11px 0; font-weight: 500"><span style="display: inline-flex; align-items: center; gap: 7px"><span aria-hidden="true" style="font-size: 9px; color: ' + couleur + '">' + icone + '</span>' + lab + '</span></th>' +
      '<td style="text-align: right; padding: 11px 0 11px 12px">' + o.n + '</td><td style="text-align: right; padding: 11px 0 11px 12px; font-weight: 600; color: ' + (o.m === null ? '#5C6068' : couleurSigne(o.m, true)) + '">' + (o.m === null ? '—' : fmt(o.m, 2) + ' pt') + '</td></tr>';
    const cp = bloc.comparaison_jours || {};
    const phrase = cp.disponible
      ? 'Différence entre jours positifs et négatifs : <strong style="color: ' + couleurSigne(cp.ecart_pts, true) + '">' + fmt(cp.ecart_pts, 2) + ' pt</strong> (p = ' + nb(cp.p, 2) + ', p corrigée = ' + nb(cp.p_holm, 2) + ') — ' + (cp.significatif_apres_correction ? 'différence significative après correction, à confirmer.' : 'pas de différence significative après correction.')
      : 'Comparaison non calculée : il faut au moins ' + (cp.requis_par_categorie || 15) + ' journées positives et ' + (cp.requis_par_categorie || 15) + ' négatives (' + (cp.n_positifs || 0) + ' et ' + (cp.n_negatifs || 0) + ' à ce jour).';
    const colComparaison = '<article style="display: flex; flex-direction: column; gap: 14px; padding: 22px 0 8px 36px; border-left: 1px solid #D8D6CF">' +
      '<h3 class="kicker">Exploratoire · Écart moyen selon l’humeur du jour</h3>' +
      '<table class="num" style="width: 100%; border-collapse: collapse; font-size: 14px"><thead><tr style="border-bottom: 1px solid #D8D6CF">' +
      '<th scope="col" style="text-align: left; padding: 6px 0 8px; font-size: 12px; font-weight: 500; color: #5C6068">Étiquette</th><th scope="col" style="text-align: right; padding: 6px 0 8px 12px; font-size: 12px; font-weight: 500; color: #5C6068">Jours</th><th scope="col" style="text-align: right; padding: 6px 0 8px 12px; font-size: 12px; font-weight: 500; color: #5C6068">Écart moyen</th></tr></thead><tbody>' +
      ligneT('▲', '#1E5E38', 'Positif', pos) + ligneT('●', '#3D4048', 'Neutre', neu) + ligneT('▼', '#9E2B22', 'Négatif', neg) +
      '<tr style="border-bottom: 1px solid #E2E0DA"><th scope="row" style="text-align: left; padding: 11px 0; font-weight: 400; color: #5C6068"><span style="display: inline-flex; align-items: center; gap: 7px"><span aria-hidden="true" style="font-size: 10px">○</span>Signal insuffisant</span></th><td style="text-align: right; padding: 11px 0 11px 12px; color: #5C6068">' + exclusInsuf + '</td><td style="text-align: right; padding: 11px 0 11px 12px; color: #5C6068">exclus</td></tr>' +
      '<tr><th scope="row" style="text-align: left; padding: 11px 0; font-weight: 400; color: #5C6068"><span style="display: inline-flex; align-items: center; gap: 7px"><span aria-hidden="true" style="font-size: 10px">◐</span>Couverture partielle</span></th><td style="text-align: right; padding: 11px 0 11px 12px; color: #5C6068">' + exclusPart + '</td><td style="text-align: right; padding: 11px 0 11px 12px; color: #5C6068">exclus</td></tr>' +
      '</tbody></table><p class="num" style="margin: 0; font-size: 13px; line-height: 1.5; color: #4A4E57">' + phrase + '</p></article>';
    $('analyse').innerHTML = '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap"><div style="display: flex; flex-direction: column; gap: 6px">' +
      '<h2 class="titre-section">Sentiment et performance : premiers résultats</h2>' +
      '<p class="num" style="margin: 0; font-size: 14px; color: #4A4E57">Solde Marché et écart quotidien de l’ETF ESG strict (SRI) face au MSCI World · ' + n + ' jours de bourse exploitables depuis le 16/10/2026</p></div></div>' +
      '<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; border-top: 1px solid #15171C">' + colPrincipal + colGlissante + colComparaison + '</div>' +
      '<p style="margin: 0; font-size: 13px; color: #5C6068">Les deux tests exploratoires servent à formuler des pistes, pas des conclusions ; leurs p-valeurs sont corrigées pour tests multiples (méthode de Holm, ' + (P.nb_tests_exploratoires_disponibles || 23) + ' tests). Méthode détaillée et limites : <button type="button" class="navlink" aria-haspopup="dialog" data-ouvrir="methodologie" style="font-size: 13px">voir la méthodologie</button>.</p>';
  }

  /* ----------------------------------------------- Sélecteurs à curseur */
  // Curseur en trois pièces (deux extrémités rondes et une partie centrale mise à l'échelle), comme la maquette.
  function curseur(seg) {
    if (!seg) return;
    let pieces = seg.querySelectorAll('.thumb');
    if (!pieces.length) {
      for (let i = 0; i < 3; i++) { const t = document.createElement('span'); t.className = 'thumb'; t.setAttribute('aria-hidden', 'true'); seg.insertBefore(t, seg.firstChild); }
      pieces = seg.querySelectorAll('.thumb');
    }
    const b = seg.querySelector('button[aria-pressed="true"]');
    if (!b || !b.offsetWidth) return;
    const x = b.offsetLeft, w = b.offsetWidth, h = b.offsetHeight;
    const [g, m, d] = pieces;
    g.style.cssText = 'width: ' + h + 'px; height: ' + h + 'px; border-radius: ' + h / 2 + 'px; transform: translateX(' + x.toFixed(1) + 'px)';
    m.style.cssText = 'width: 100px; height: ' + h + 'px; transform-origin: 0 50%; transform: translateX(' + (x + h / 2).toFixed(1) + 'px) scaleX(' + (Math.max(0, w - h) / 100).toFixed(4) + ')';
    d.style.cssText = 'width: ' + h + 'px; height: ' + h + 'px; border-radius: ' + h / 2 + 'px; transform: translateX(' + (x + w - h).toFixed(1) + 'px)';
    seg.classList.add('mesure');
  }
  function majCurseurs() { document.querySelectorAll('.seg').forEach(curseur); }
  function presser(seg, valeur) {
    seg.querySelectorAll('button[data-valeur]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.valeur === valeur ? 'true' : 'false'));
    curseur(seg);
  }

  /* --------------------------------------------- Changement de sélection */
  // Les zones s'effacent puis réapparaissent avec les nouvelles valeurs (aucune valeur intermédiaire inventée).
  function basculer(zones, maj) {
    zones = zones.filter(Boolean);
    zones.forEach((z) => z.classList.add('sortie'));
    setTimeout(() => { maj(); zones.forEach((z) => z.classList.remove('sortie')); }, reduit ? 150 : 120);
  }
  function choisir(patch) {
    const avant = { periode: S.periode, etf: S.etf, grp: S.grp };
    Object.assign(S, patch);
    if (avant.periode === S.periode && avant.etf === S.etf && avant.grp === S.grp) return;
    const E = etatEcran();
    const zones = [$('zone-courbe'), $('g-axe'), $('zone-barres'), $('g-dates')];
    if (avant.periode !== S.periode) zones.push($('kx-zone'));
    if (avant.etf !== S.etf) zones.push($('synthese-texte'));
    masquerInfobulle();
    basculer(zones, () => {
      rendreGraphique(E);
      if (avant.periode !== S.periode) rendreCarteEcart(E);
      if (avant.etf !== S.etf) rendreSynthese(E);
    });
  }
  function brancherSelecteurs() {
    $('etf-a').addEventListener('change', (ev) => choisir({ etf: ev.target.value }));
    document.querySelectorAll('#seg-groupe button').forEach((b) => b.addEventListener('click', () => { presser($('seg-groupe'), b.dataset.valeur); choisir({ grp: b.dataset.valeur }); }));
    document.querySelectorAll('#seg-periode button').forEach((b) => b.addEventListener('click', () => { presser($('seg-periode'), b.dataset.valeur); choisir({ periode: b.dataset.valeur }); }));
    window.addEventListener('resize', () => { majCurseurs(); masquerInfobulle(); });
    try { if (document.fonts && document.fonts.ready) document.fonts.ready.then(majCurseurs); } catch (e) {}
  }

  /* =========================================================== Panneaux */
  const TITRES_PANNEAUX = { titres: 'Titres du jour', secteurs: 'Répartition par secteur', reglementaire: 'Données réglementaires', methodologie: 'Méthodologie' };
  let declencheur = null, minuterieFermeture = 0;

  function piedPanneau(sources, avecModele) {
    return '<footer class="pied" style="animation: none"><p style="margin: 0; max-width: 760px">' + sources + '</p>' +
      (avecModele ? '<p style="margin: 0" class="credit-modele">Modèle de sentiment : FinBERT (ProsusAI) — © MIH AI B.V., licence CC BY-NC-SA 4.0</p>' : '') + '</footer>';
  }
  const SOURCE_TITRES = 'Sources : titres de presse — flux RSS publics de la presse financière (CNBC, Wall Street Journal, Financial Times, Bloomberg, BBC, The Guardian, New York Times, Euronews, Deutsche Welle) et de la finance durable (ESG Today, ESG Dive, ESG News, Responsible Investor, Trellis, Edie…), complétés par Google Actualités ; liste complète dans la méthodologie. Titres relevés toutes les 3 heures, scores calculés au relevé.';

  /* --- Titres du jour --- */
  function contenuTitres() {
    const se = D.sentiment;
    if (!se || !se.groupes) return '<p class="intro-panneau">Pas encore de journée de sentiment close.</p>';
    const tg = S.tgrp, g = se.groupes[tg] || {}, label = tg === 'esg' ? 'ESG' : 'Marché';
    const t = ETIQUETTES[g.etiquette] || ETIQUETTES['neutre'];
    const liste = (titres, couleur, signe) => {
      if (!titres || !titres.length) return '<li style="padding: 18px 0; border-bottom: 1px solid #D8D6CF; font-size: 15px; color: #5C6068">Aucun titre classé ' + (signe > 0 ? 'positif' : 'négatif') + ' pour cette journée.</li>';
      return titres.map((h, i) => '<li style="display: grid; grid-template-columns: 30px minmax(0, 1fr) 72px; column-gap: 14px; padding: 18px 0; border-bottom: 1px solid #D8D6CF">' +
        '<span class="num" style="font-family: \'Newsreader\', Georgia, serif; font-size: 22px; line-height: 1.2; color: #5C6068">' + (i + 1) + '</span>' +
        '<div style="display: flex; flex-direction: column; gap: 8px; min-width: 0"><p lang="en" style="margin: 0; font-family: \'Newsreader\', Georgia, serif; font-size: 21px; line-height: 1.3; text-wrap: pretty">' + esc(h.titre) + '</p>' +
        '<div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; font-size: 13px; color: #5C6068"><span>' + esc(h.source) + '</span>' +
        '<a href="' + esc(h.lien) + '" target="_blank" rel="noopener noreferrer" aria-label="Lire l’article : ' + esc(h.titre) + ' (nouvel onglet)" style="display: inline-flex; align-items: center; gap: 4px; font-weight: 500">Lire l’article<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M4 2h6v6M10 2L3 9"></path></svg></a></div></div>' +
        '<span class="num" title="p(positif) ' + nb(h.p_positif, 3) + ' − p(négatif) ' + nb(h.p_negatif, 3) + '" style="text-align: right; font-size: 17px; font-weight: 600; line-height: 1.5; color: ' + couleur + '">' + fmt(h.score, 2) + '</span></li>').join('');
    };
    const soldeCouleur = g.etiquette === 'signal insuffisant' ? '#3D4048' : t.valeur;
    return '<section aria-label="Présentation" class="presentation"><p class="num kicker" style="margin: 10px 0 0">Séance du ' + jjmmaaaa(se.derniere_seance) + '</p>' +
      '<div style="display: flex; flex-direction: column; gap: 12px"><h1 class="titre-panneau">Titres du jour</h1>' +
      '<p class="intro-panneau">Les cinq titres les plus positifs et les cinq plus négatifs de la journée de bourse, pour chaque groupe. Le score va de −1 (très négatif) à +1 (très positif) : c’est la probabilité « positif » moins la probabilité « négatif » attribuées par FinBERT au titre et au début de son résumé, dans leur langue d’origine.</p></div></section>' +
      '<section aria-label="Choix du groupe" style="display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap; padding: 18px 0; border-top: 1px solid #D8D6CF; border-bottom: 1px solid #D8D6CF">' +
      '<div class="seg seg-titres" role="group" aria-label="Groupe de titres" id="seg-titres"><button type="button" class="press" aria-pressed="' + (tg === 'marche') + '" data-valeur="marche">Marché</button><button type="button" class="press" aria-pressed="' + (tg === 'esg') + '" data-valeur="esg">ESG</button></div>' +
      '<div class="num" style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 14px; color: #4A4E57"><span>Humeur ' + label + '</span>' + tagHtml(g.etiquette) +
      '<span>solde <strong style="color: ' + soldeCouleur + '">' + fmt(g.solde, 1) + '</strong> · marge ± ' + nb(g.marge_erreur, 1) + ' · ' + (g.nb_articles || 0) + ' articles analysés</span></div></section>' +
      '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(480px, 100%), 1fr)); gap: 64px">' +
      '<section aria-labelledby="t-pos" style="display: flex; flex-direction: column; gap: 4px"><h2 id="t-pos" class="titre-liste"><span aria-hidden="true" style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 12px; color: #1E5E38">▲</span>Les plus positifs</h2><ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column">' + liste(g.plus_positifs, '#1E5E38', 1) + '</ol></section>' +
      '<section aria-labelledby="t-neg" style="display: flex; flex-direction: column; gap: 4px"><h2 id="t-neg" class="titre-liste"><span aria-hidden="true" style="font-family: \'IBM Plex Sans\', sans-serif; font-size: 12px; color: #9E2B22">▼</span>Les plus négatifs</h2><ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column">' + liste(g.plus_negatifs, '#9E2B22', -1) + '</ol></section></div>' +
      piedPanneau(SOURCE_TITRES, true);
  }
  function brancherTitres() {
    const seg = $('seg-titres');
    if (!seg) return;
    curseur(seg);
    seg.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      if (S.tgrp === b.dataset.valeur) return;
      S.tgrp = b.dataset.valeur;
      const cont = $('panneau-contenu');
      cont.innerHTML = contenuTitres();
      brancherTitres();
      $('seg-titres').querySelector('button[data-valeur="' + S.tgrp + '"]').focus({ preventScroll: true });
    }));
  }

  /* --- Répartition par secteur --- */
  function pctS(v) { return (v === null || v === undefined) ? '—' : nb(v, 1) + ' %'; }
  function introSecteurs(sec) {
    const c = sec.compositions || {}, ref = c.msci_world;
    if (!ref) return '';
    const IT = 'Technologies de l\'information', EN = 'Énergie';
    const gt = (id) => c[id] && c[id].grandes_tech.total_pct, sp = (id, s) => c[id] && (c[id].secteurs_pct[s] || 0);
    const phrases = [];
    const decrit = (id, nom) => {
      if (!c[id]) return;
      const en = sp(id, EN), r = gt(id) / gt('msci_world');
      const energie = en < 0.5 ? 'ne détient presque pas d’énergie (' + pctS(en) + ')' : (en < sp('msci_world', EN) * 0.75 ? 'détient moins d’énergie (' + pctS(en) + ')' : 'détient autant d’énergie (' + pctS(en) + ')');
      const geants = r < 0.7 ? 'pèse nettement moins sur les sept géants technologiques américains (' + pctS(gt(id)) + ')' : (r > 1.03 ? 'pèse un peu plus sur les sept géants technologiques américains (' + pctS(gt(id)) + ')' : 'pèse autant sur les sept géants technologiques américains (' + pctS(gt(id)) + ')');
      phrases.push(nom + ' ' + energie + ' et ' + geants + (id === 'sri' ? ', alors que sa part du secteur technologique reste proche de celle de l’indice (' + pctS(sp(id, IT)) + ' contre ' + pctS(sp('msci_world', IT)) + ')' : '') + '.');
    };
    decrit('sri', 'L’ETF ESG strict (SRI)');
    decrit('paris', 'L’ETF Paris-Aligned');
    decrit('screened', 'L’ETF Screened');
    return 'Au ' + jjmmaaaa(ref.date_composition) + ', le MSCI World compte ' + pctS(sp('msci_world', EN)) + ' d’énergie et ' + pctS(gt('msci_world')) + ' pour les sept géants technologiques américains (Apple, Nvidia, Microsoft, Amazon, Alphabet, Meta, Tesla). ' + phrases.join(' ');
  }
  function effetSecteurs(sec) {
    const ef = sec.effet_sectoriel || {}, s = ef.sri;
    if (!s || !s.parts_de_l_ecart_pct) return '';
    const parts = s.parts_de_l_ecart_pct;
    let t = 'Mesure sur trois ans (du ' + jjmmaaaa(s.debut) + ' au ' + jjmmaaaa(s.fin) + ') : environ ' + parts.grandes_tech + ' % du retard relatif de l’ETF SRI (' + fmt(s.ecart_relatif_pct, 1) + ' %) s’explique par sa sous-pondération des géants technologiques ; l’énergie n’a presque pas compté (' + fmt(parts.energie, 0) + ' %).';
    if (ef.bnp_sri_pab && ef.bnp_sri_pab.parts_de_l_ecart_pct) t += ' Pour le BNP Easy SRI PAB, la part est d’environ ' + ef.bnp_sri_pab.parts_de_l_ecart_pct.grandes_tech + ' %.';
    return t;
  }
  function contenuSecteurs() {
    const sec = D.secteurs;
    if (!sec || !sec.compositions || !sec.compositions.msci_world) return '<p class="intro-panneau">Données sectorielles indisponibles.</p>';
    const c = sec.compositions, ref = c.msci_world, id = S.secEtf, e = c[id];
    const ordre = Object.keys(ref.secteurs_pct).filter((s) => s !== 'Liquidités et autres');
    const IT = 'Technologies de l\'information', EN = 'Énergie';
    const options = ['sri', 'screened', 'paris', 'bnp_sri_pab'].map((k) => '<option value="' + k + '"' + (k === id ? ' selected' : '') + '>' + esc(ETF[k].label + (k === 'bnp_sri_pab' ? ' (complément)' : '')) + '</option>').join('');
    let corps;
    if (!e) {
      corps = '<p style="margin: 0; padding: 22px 0; border-top: 1px solid #15171C; font-size: 15px; color: #4A4E57">Composition non disponible pour ce fonds : le site de l’émetteur ne publie pas de fichier de composition exploitable automatiquement.</p>';
    } else {
      const detail = Object.entries(e.grandes_tech.detail).map(([n, v]) => n + ' ' + pctS(v)).join(', ');
      const lignes = ordre.map((s) => {
        const ve = e.secteurs_pct[s] || 0, vr = ref.secteurs_pct[s] || 0, d = ve - vr;
        const sc = (Math.min(Math.abs(d), 8) / 8).toFixed(4), cle = s === IT || s === EN;
        const g = Math.round(d * 10) / 10, gap = g === 0 ? '0,0' : (g > 0 ? '+' : '−') + Math.abs(g).toFixed(1).replace('.', ',');
        return '<div role="row" class="ligne-secteur" style="background: ' + (cle ? 'rgba(21, 23, 28, 0.045)' : 'transparent') + '">' +
          '<span role="rowheader" style="font-size: 15px; font-weight: ' + (cle ? 600 : 400) + '">' + esc(s) + '</span>' +
          '<span role="cell" class="num" style="text-align: right; font-size: 15px">' + pctS(ve) + '</span>' +
          '<span role="cell" class="num" style="text-align: right; font-size: 15px; color: #4A4E57">' + pctS(vr) + '</span>' +
          '<div role="cell" aria-label="Écart de pondération ' + gap + ' point" style="position: relative; height: 44px"><div style="position: absolute; left: 50%; top: 8px; bottom: 8px; width: 1px; background: #8E8C85"></div>' +
          '<div style="position: absolute; top: 15px; height: 14px; right: 50%; width: 50%; background: #15171C; transform-origin: 100% 50%; transform: scaleX(' + (d < 0 ? sc : 0) + ')"></div>' +
          '<div style="position: absolute; top: 15px; height: 14px; left: 50%; width: 50%; background: #9A9890; transform-origin: 0 50%; transform: scaleX(' + (d > 0 ? sc : 0) + ')"></div></div>' +
          '<span role="cell" class="num" style="text-align: right; font-size: 15px; font-weight: ' + (cle ? 600 : 400) + '">' + gap + '</span></div>';
      }).join('');
      corps = '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0; border-top: 1px solid #15171C; border-bottom: 1px solid #D8D6CF">' +
        '<div style="display: flex; flex-direction: column; gap: 8px; padding: 22px 32px 22px 0; border-right: 1px solid #D8D6CF"><h3 class="kicker">Énergie</h3><p class="num" style="margin: 0; display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap"><span style="font-family: \'Newsreader\', Georgia, serif; font-size: 48px; line-height: 1; font-weight: 500">' + pctS(e.secteurs_pct[EN] || 0) + '</span><span style="font-size: 15px; color: #4A4E57">contre ' + pctS(ref.secteurs_pct[EN]) + ' dans le MSCI World</span></p></div>' +
        '<div style="display: flex; flex-direction: column; gap: 8px; padding: 22px 0 22px 32px"><h3 class="kicker" style="display: flex; align-items: center; gap: 8px">Sept plus grandes valeurs technologiques <button type="button" class="tip bouton-aide" aria-label="Détail des positions">?<span class="tipbox" role="tooltip">Apple, Microsoft, Nvidia, Amazon, Alphabet (deux catégories d’actions), Meta et Tesla. Détenues par cet ETF : ' + esc(detail || 'aucune') + '.</span></button></h3><p class="num" style="margin: 0; display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap"><span style="font-family: \'Newsreader\', Georgia, serif; font-size: 48px; line-height: 1; font-weight: 500">' + pctS(e.grandes_tech.total_pct) + '</span><span style="font-size: 15px; color: #4A4E57">contre ' + pctS(ref.grandes_tech.total_pct) + ' dans le MSCI World</span></p></div></div>' +
        '<div role="table" aria-label="Pondérations sectorielles et écarts" style="display: flex; flex-direction: column"><div role="row" class="ligne-secteur entete-secteur">' +
        '<span role="columnheader">Secteur</span><span role="columnheader" style="text-align: right">' + esc(ETF[id].court) + '</span><span role="columnheader" style="text-align: right">MSCI World</span>' +
        '<div role="columnheader" style="position: relative; height: 32px"><span style="position: absolute; left: 0; top: 0">Écart de pondération</span><span class="num" style="position: absolute; left: 0; bottom: 0; font-weight: 400; color: #5C6068">−8</span><span class="num" style="position: absolute; left: 25%; bottom: 0; transform: translateX(-50%); font-weight: 400; color: #5C6068">−4</span><span class="num" style="position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); font-weight: 400; color: #5C6068">0</span><span class="num" style="position: absolute; left: 75%; bottom: 0; transform: translateX(-50%); font-weight: 400; color: #5C6068">+4</span><span class="num" style="position: absolute; right: 0; bottom: 0; font-weight: 400; color: #5C6068">+8</span></div>' +
        '<span role="columnheader" style="text-align: right">Écart (pt)</span></div>' + lignes + '</div>' +
        '<div style="display: flex; align-items: center; gap: 26px; flex-wrap: wrap; font-size: 13px; color: #4A4E57"><span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 14px; height: 10px; background: #15171C"></span>Sous-pondération par rapport au MSCI World</span><span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 14px; height: 10px; background: #9A9890"></span>Surpondération</span></div>';
    }
    const dateCompo = jjmmaaaa(ref.date_composition);
    return '<section aria-label="Présentation" class="presentation"><p class="kicker" style="margin: 10px 0 0">Composition des portefeuilles</p>' +
      '<div style="display: flex; flex-direction: column; gap: 16px"><h1 class="titre-panneau">Répartition par secteur</h1>' +
      '<p style="margin: 0; max-width: 820px; font-family: \'Newsreader\', Georgia, serif; font-size: 22px; line-height: 1.45; text-wrap: pretty">' + esc(introSecteurs(sec)) + '</p>' +
      '<p style="margin: 0; max-width: 820px; font-size: 15px; line-height: 1.55; color: #4A4E57">' + esc(effetSecteurs(sec)) + ' ' + esc(sec.avertissement_periode || '') + '</p>' +
      '<p style="margin: 0; font-size: 14px; color: #5C6068">Composition au ' + dateCompo + ', d’après les fichiers officiels des fonds iShares ; mesure de l’effet des paris sur trois ans détaillée dans la méthodologie.</p></div></section>' +
      '<section aria-label="Écarts de pondération" style="display: flex; flex-direction: column; gap: 28px; padding-top: 28px; border-top: 1px solid #D8D6CF">' +
      '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap"><div style="display: flex; flex-direction: column; gap: 6px"><h2 class="titre-section">' + esc(ETF[id].label) + ' face au MSCI World</h2><p style="margin: 0; font-size: 14px; color: #4A4E57">Poids de chaque secteur dans le portefeuille, en % · écart en points de pourcentage</p></div>' +
      '<div style="display: flex; align-items: center; gap: 8px"><label for="etf-sp" style="font-size: 13px; color: #4A4E57">ETF</label><select id="etf-sp" class="choix">' + options + '</select></div></div>' +
      '<div class="fondu-zone" id="zone-secteurs" style="display: flex; flex-direction: column; gap: 28px">' + corps + '</div></section>' +
      piedPanneau('Sources : composition des portefeuilles — fichiers officiels de composition des fonds iShares (BlackRock), au ' + dateCompo + ' ; cours des ETF et des facteurs « grandes valeurs technologiques » et « énergie » — Yahoo Finance (cotations Xetra). Composition rafraîchie chaque semaine.', false);
  }
  function brancherSecteurs() {
    const sel = $('etf-sp');
    if (!sel) return;
    sel.addEventListener('change', () => {
      S.secEtf = sel.value;
      basculer([$('zone-secteurs')], () => {
        const cont = $('panneau-contenu'), y = $('panneau').scrollTop;
        cont.innerHTML = contenuSecteurs();
        brancherSecteurs();
        $('panneau').scrollTop = y;
        $('etf-sp').focus({ preventScroll: true });
      });
    });
  }

  /* --- Données réglementaires --- */
  function contenuReglementaire() {
    const fiches = Object.fromEntries((D.performance.etf || []).map((f) => [f.id, f]));
    const dateNote = (Object.values(fiches).find((f) => f.note_msci && f.note_msci.date) || {}).note_msci;
    const verifie = (Object.values(fiches).find((f) => f.verifie_le) || {}).verifie_le;
    const sfdr = (s) => /article 6/i.test(s || '') ? 'Article 6' : esc(s || '—');
    const isr = (f) => (f.labels || []).some((l) => /label isr/i.test(l.nom || ''));
    const pastille = (oui) => oui
      ? '<span style="display: inline-flex; align-items: center; gap: 8px; font-weight: 600"><span aria-hidden="true" style="width: 9px; height: 9px; border-radius: 50%; background: #15171C"></span>Oui</span>'
      : '<span style="display: inline-flex; align-items: center; gap: 8px; color: #4A4E57"><span aria-hidden="true" style="width: 9px; height: 9px; border-radius: 50%; border: 1.5px solid #8E8C85; box-sizing: border-box"></span>Non</span>';
    const note = (f) => {
      if (f.note_msci && f.note_msci.note) return '<span style="display: inline-flex; align-items: center; justify-content: center; min-width: 40px; height: 28px; padding: 0 8px; box-sizing: border-box; border: 1px solid #15171C; font-family: \'Newsreader\', Georgia, serif; font-size: 17px; font-weight: 500">' + esc(f.note_msci.note) + '</span>';
      const txt = f.id === 'msci_world' ? 'Non publiée' : 'Non disponible';
      return '<span style="display: inline-flex; align-items: center; gap: 6px; font-style: italic; color: #5C6068">' + txt + (f.note_msci_commentaire ? '<button type="button" class="tip bouton-aide" style="font-style: normal" aria-label="Pourquoi ?">?<span class="tipbox" role="tooltip">' + esc(f.note_msci_commentaire) + '</span></button>' : '') + '</span>';
    };
    const ligne = (id, complement) => {
      const f = fiches[id];
      if (!f) return '';
      const nom = id === 'msci_world' ? 'MSCI World <span style="font-weight: 400; color: #5C6068">(référence)</span>' : esc(ETF[id].label);
      return '<tr style="border-bottom: 1px solid #D8D6CF">' +
        '<th scope="row" style="text-align: left; padding: 18px 0; font-weight: ' + (id === 'msci_world' ? 600 : (complement ? 400 : 500)) + (complement ? '; font-style: italic; color: #4A4E57' : '') + '">' + nom + '</th>' +
        '<td style="padding: 18px 16px' + (complement ? '; color: #4A4E57' : '') + '">' + sfdr(f.sfdr) + '</td>' +
        '<td style="padding: 18px 16px">' + pastille(isr(f)) + '</td>' +
        '<td style="padding: 18px 16px">' + note(f) + '</td>' +
        '<td style="text-align: right; padding: 18px 0 18px 16px' + (complement ? '; color: #4A4E57' : '') + '">' + nb(f.frais_annuels_pct, 2) + ' %</td></tr>';
    };
    const repere = (titre, texte) => '<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 16px; border-top: 1px solid #D8D6CF"><dt class="kicker">' + titre + '</dt><dd style="margin: 0; font-family: \'Newsreader\', Georgia, serif; font-size: 18px; line-height: 1.55; text-wrap: pretty">' + texte + '</dd></div>';
    return '<section aria-label="Présentation" class="presentation"><p class="kicker" style="margin: 10px 0 0">Fiches des fonds</p>' +
      '<div style="display: flex; flex-direction: column; gap: 12px"><h1 class="titre-panneau">Données réglementaires</h1>' +
      '<p class="intro-panneau">Classification européenne, label public français, notation extra-financière et frais : ce que chaque fonds déclare, au même endroit.</p></div></section>' +
      '<section aria-label="Tableau réglementaire" style="display: flex; flex-direction: column; gap: 12px"><table class="num" style="width: 100%; border-collapse: collapse; font-size: 15px"><thead><tr style="border-bottom: 1px solid #15171C">' +
      '<th scope="col" style="width: 30%; text-align: left; padding: 12px 0; font-size: 12px; font-weight: 600; color: #4A4E57">Fonds</th>' +
      '<th scope="col" style="text-align: left; padding: 12px 16px; font-size: 12px; font-weight: 600; color: #4A4E57">Classification SFDR</th>' +
      '<th scope="col" style="text-align: left; padding: 12px 16px; font-size: 12px; font-weight: 600; color: #4A4E57">Label ISR</th>' +
      '<th scope="col" style="text-align: left; padding: 12px 16px; font-size: 12px; font-weight: 600; color: #4A4E57">Note MSCI ESG <span style="font-weight: 400; color: #5C6068">au ' + (dateNote ? jjmmaaaa(dateNote.date) : '—') + '</span></th>' +
      '<th scope="col" style="text-align: right; padding: 12px 0 12px 16px; font-size: 12px; font-weight: 600; color: #4A4E57">Frais courants annuels</th></tr></thead><tbody>' +
      ligne('msci_world') + ligne('screened') + ligne('sri') + ligne('paris') +
      '<tr><td colspan="5" style="padding: 22px 0 8px; font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #5C6068; border-bottom: 1px dashed #B4B2AB">Complément</td></tr>' +
      ligne('bnp_sri_pab', true) + '</tbody></table>' +
      '<p style="margin: 0; font-size: 13px; color: #5C6068">Frais courants prélevés chaque année par l’émetteur, déjà déduits des performances affichées sur Contrepoint. Données relevées à la main dans les documents officiels, vérifiées le ' + (verifie ? jjmmaaaa(verifie) : '—') + '.</p></section>' +
      '<section aria-label="Repères" style="display: flex; flex-direction: column; gap: 20px; padding-top: 28px; border-top: 3px double #15171C"><h2 class="titre-section">Repères</h2>' +
      '<dl style="margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(480px, 100%), 1fr)); column-gap: 56px; row-gap: 28px">' +
      repere('Classification SFDR', 'Règlement européen 2019/2088 sur la publication d’informations en matière de durabilité. L’article 6 vise les fonds qui ne mettent en avant aucune caractéristique de durabilité ; l’article 8, ceux qui promeuvent des caractéristiques environnementales ou sociales ; l’article 9, ceux qui poursuivent un objectif d’investissement durable.') +
      repere('Label ISR', 'Label public français de l’investissement socialement responsable, créé en 2016 et réformé en 2024. Le nouveau référentiel renforce les exigences, notamment en excluant les entreprises qui lancent de nouveaux projets d’exploration ou de production d’hydrocarbures.') +
      repere('Note MSCI ESG', 'Notation attribuée par MSCI selon l’exposition des entreprises en portefeuille aux risques environnementaux, sociaux et de gouvernance, et la manière dont elles les gèrent. L’échelle va de CCC, la plus faible, à AAA, la meilleure.') +
      repere('Frais courants', 'Coût annuel de gestion du fonds, exprimé en pourcentage de l’encours. Il est prélevé en continu sur l’actif : un écart de 0,05 point paraît faible, mais il se cumule d’année en année.') +
      '</dl></section>' +
      piedPanneau('Sources : documents réglementaires des émetteurs — fiches et prospectus iShares (BlackRock) et BNP Paribas Asset Management ; label ISR — liste officielle des fonds labellisés au 30/09/2026 ; label Greenfin — liste du ministère de la Transition écologique ; notes MSCI ESG au ' + (dateNote ? jjmmaaaa(dateNote.date) : '—') + ' — MSCI ESG Research, publiées dans les fiches iShares.', false);
  }

  /* --- Méthodologie --- */
  function contenuMethodologie() {
    const m = D.methodologie;
    if (!m) return '<p class="intro-panneau">Méthodologie indisponible.</p>';
    const sommaire = m.sommaire.map((s) => '<li style="border-bottom: 1px solid #D8D6CF"><a href="#' + esc(s.id) + '" data-ancre="' + esc(s.id) + '" style="display: flex; gap: 12px; padding: 11px 0; font-size: 14px"><span class="num" style="color: #5C6068">' + esc(s.numero) + '</span>' + esc(s.titre) + '</a></li>').join('');
    return '<div style="display: flex; flex-wrap: wrap; gap: 64px; align-items: flex-start; padding-top: 8px">' +
      '<aside aria-label="Sommaire" style="flex: 1 1 220px; max-width: 260px; display: flex; flex-direction: column; gap: 14px; position: sticky; top: 84px"><p class="kicker">Sommaire</p><ol style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; border-top: 1px solid #15171C">' + sommaire + '</ol></aside>' +
      '<article class="prose" style="flex: 999 1 520px; min-width: 0; max-width: 700px"><p style="margin: 0 0 14px; font-family: \'IBM Plex Sans\', Arial, sans-serif; font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #4A4E57">Comment lire Contrepoint</p>' +
      '<h1 style="margin: 0 0 24px; font-family: \'Newsreader\', Georgia, serif; font-weight: 500; font-size: 56px; line-height: 1.05; letter-spacing: -0.01em">Méthodologie</h1>' + m.html + '</article></div>' +
      piedPanneau('Sources : cours des ETF et de l’indice MSCI World — Yahoo Finance (usage personnel, non commercial) ; taux de change et €STR — Banque centrale européenne ; titres de presse — flux RSS publics listés dans config/flux_rss.yaml. Texte de référence : contenu/methodologie.md du dépôt.', true);
  }
  function brancherMethodologie() {
    // Liens du sommaire : défilement interne au panneau (sans changer l'adresse de la page).
    $('panneau-contenu').querySelectorAll('a[data-ancre]').forEach((a) => a.addEventListener('click', (ev) => {
      ev.preventDefault();
      const cible = document.getElementById(a.dataset.ancre);
      if (cible) { cible.scrollIntoView({ behavior: reduit ? 'auto' : 'smooth', block: 'start' }); cible.setAttribute('tabindex', '-1'); cible.focus({ preventScroll: true }); }
    }));
  }

  /* --- Ouverture et fermeture --- */
  function remplirPanneau(id) {
    const cont = $('panneau-contenu');
    cont.innerHTML = id === 'titres' ? contenuTitres() : id === 'secteurs' ? contenuSecteurs() : id === 'reglementaire' ? contenuReglementaire() : contenuMethodologie();
    if (id === 'titres') brancherTitres();
    if (id === 'secteurs') brancherSecteurs();
    if (id === 'methodologie') brancherMethodologie();
    $('panneau').setAttribute('aria-label', TITRES_PANNEAUX[id]);
    $('panneau').scrollTop = 0;
  }
  function ouvrir(id, declencheurEl, immediat) {
    if (!TITRES_PANNEAUX[id]) return;
    clearTimeout(minuterieFermeture);
    declencheur = declencheurEl || document.activeElement;
    remplirPanneau(id);
    const p = $('panneau'), v = $('voile');
    S.panneau = id;
    p.hidden = false; v.hidden = false;
    document.documentElement.classList.add('panneau-ouvert');
    if (immediat) {
      p.style.transition = 'none'; v.style.transition = 'none';
      p.style.transform = 'none'; p.style.opacity = '1'; v.style.opacity = '1';
    } else {
      p.style.transition = 'none'; v.style.transition = 'none';
      p.style.transform = reduit ? 'none' : 'translateX(100%)'; p.style.opacity = reduit ? '0' : '1'; v.style.opacity = '0';
      void p.offsetWidth; // l'état de départ est appliqué avant la transition
      requestAnimationFrame(() => requestAnimationFrame(() => {
        p.style.transition = reduit ? 'opacity 150ms ease-out' : 'transform 420ms cubic-bezier(0.32, 0.72, 0, 1)';
        v.style.transition = reduit ? 'opacity 150ms ease-out' : 'opacity 300ms cubic-bezier(0.22, 1, 0.36, 1)';
        p.style.transform = 'none'; p.style.opacity = '1'; v.style.opacity = '1';
      }));
    }
    requestAnimationFrame(() => { majCurseurs(); const b = p.querySelector('[data-fermer]'); if (b) b.focus({ preventScroll: true }); });
    if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
  }
  function fermer() {
    if (!S.panneau || S.phase === 'sortie') return;
    S.phase = 'sortie';
    const p = $('panneau'), v = $('voile');
    p.style.transition = reduit ? 'opacity 150ms ease-out' : 'transform 260ms cubic-bezier(0.32, 0, 0.67, 0)';
    v.style.transition = reduit ? 'opacity 150ms ease-out' : 'opacity 200ms cubic-bezier(0.32, 0, 0.67, 0)';
    if (reduit) p.style.opacity = '0'; else p.style.transform = 'translateX(100%)';
    v.style.opacity = '0';
    minuterieFermeture = setTimeout(() => {
      p.hidden = true; v.hidden = true; S.panneau = null; S.phase = null;
      document.documentElement.classList.remove('panneau-ouvert');
      history.replaceState(null, '', location.pathname + location.search);
      if (declencheur && declencheur.focus && document.contains(declencheur)) declencheur.focus({ preventScroll: true });
    }, reduit ? 150 : 260);
  }
  function brancherPanneaux() {
    document.addEventListener('click', (ev) => {
      const o = ev.target.closest('[data-ouvrir]');
      if (o) { ev.preventDefault(); ouvrir(o.dataset.ouvrir, o); return; }
      if (ev.target.closest('[data-fermer]') || ev.target === $('voile')) fermer();
    });
    $('panneau').addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') { ev.stopPropagation(); fermer(); return; }
      if (ev.key === 'Tab') {
        // Le focus reste dans le panneau tant qu'il est ouvert.
        const f = Array.from($('panneau').querySelectorAll('a[href], button:not([disabled]), select, [tabindex]:not([tabindex="-1"])')).filter((x) => x.offsetParent !== null);
        if (!f.length) return;
        const premier = f[0], dernier = f[f.length - 1];
        if (ev.shiftKey && document.activeElement === premier) { ev.preventDefault(); dernier.focus(); }
        else if (!ev.shiftKey && document.activeElement === dernier) { ev.preventDefault(); premier.focus(); }
      }
    });
    window.addEventListener('hashchange', () => {
      const id = location.hash.slice(1);
      if (TITRES_PANNEAUX[id] && S.panneau !== id) ouvrir(id, null, false);
      else if (!TITRES_PANNEAUX[id] && S.panneau) fermer();
    });
  }

  /* ============================================================ Démarrage */
  async function demarrer() {
    brancherPanneaux();
    if (!(await charger())) { document.body.classList.add('pret'); return; }
    const E = etatEcran();
    $('etf-a').value = S.etf;
    presser($('seg-periode'), S.periode);
    presser($('seg-groupe'), S.grp);
    rendreBandeau(E);
    rendreCarte('carte-marche', 'marche', 'Marché', E);
    rendreCarte('carte-esg', 'esg', 'ESG', E);
    rendreCarteEcart(E);
    rendreSynthese(E);
    rendreGraphique(E);
    rendreTableau(E);
    rendreVolet3();
    brancherGraphique();
    brancherSelecteurs();
    majCurseurs();
    // Les animations d'apparition démarrent maintenant que tout est rempli.
    requestAnimationFrame(() => { document.body.classList.add('pret'); majCurseurs(); });
    setTimeout(() => document.body.classList.add('pret'), 400); // si l'onglet est en arrière-plan (images suspendues)
    const id = location.hash.slice(1);
    if (TITRES_PANNEAUX[id]) ouvrir(id, null, true);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer); else demarrer();
})();
