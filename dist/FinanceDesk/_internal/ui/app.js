/**
 * FinanceDesk v1.1 — app.js
 * Connecte la maquette HTML à la bridge Python via window.pywebview.api
 * Pattern : api(methode, args) → JSON → render dans le tableau existant
 */

'use strict';

// ── Utilitaire principal ──────────────────────────────────────────────────────

async function api(method, ...args) {
  try {
    const raw  = await window.pywebview.api[method](...args);
    const data = JSON.parse(raw);
    if (!data.ok) throw new Error(data.erreur || 'Erreur inconnue');
    return data.data;
  } catch (e) {
    console.error(`[API] ${method}:`, e.message);
    throw e;
  }
}

function fmt(montant) {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency: 'EUR'
  }).format(montant ?? 0);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR');
}

function badge(statut) {
  const map = {
    'en_attente': ['badge-orange', 'En attente'],
    'payee':      ['badge-green',  'Payée'],
    'retard':     ['badge-red',    'En retard'],
    'actif':      ['badge-blue',   'Actif'],
    'envoye':     ['badge-green',  'Envoyé'],
    'desactive':  ['badge-neutral','Désactivé'],
    'ok':         ['badge-green',  'OK'],
    'attention':  ['badge-orange', 'Attention'],
    'critique':   ['badge-red',    'Critique'],
    'urgent':     ['badge-red',    'Urgent'],
    'bientot':    ['badge-orange', 'Bientôt'],
    'normal':     ['badge-neutral','En attente'],
  };
  const [cls, label] = map[statut] || ['badge-neutral', statut];
  return `<span class="badge ${cls}">${label}</span>`;
}

function showNotif(msg, type = 'success') {
  // Crée une notification toast temporaire
  const n = document.createElement('div');
  n.className = `toast toast-${type}`;
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.classList.add('show'), 10);
  setTimeout(() => { n.classList.remove('show'); setTimeout(() => n.remove(), 300); }, 3000);
}

// ══════════════════════════════════════════════════════════════════════════════
//  DÉMARRAGE
// ══════════════════════════════════════════════════════════════════════════════

window.addEventListener('pywebviewready', async () => {
  const info = await api('demarrage');

  if (info.alerte_caisse) {
    showNotif(`⚠ Solde caisse bas : ${fmt(info.solde_caisse)}`, 'warning');
  }
  if (info.rappels_envoyes > 0) {
    showNotif(`${info.rappels_envoyes} rappel(s) envoyé(s) automatiquement`, 'info');
  }

  await chargerDashboard();
  await remplirSelectBudgets();
});

// ══════════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

async function chargerDashboard() {
  try {
    const d = await api('get_dashboard');

    // KPI factures
    setText('kpi-a-payer',    fmt(d.factures.total_a_payer));
    setText('kpi-en-retard',  d.factures.nb_en_retard);
    setText('kpi-payees-mois',fmt(d.factures.total_payees_mois));

    // KPI caisse
    setText('kpi-solde-caisse', fmt(d.caisse.solde));

    // KPI recettes
    setText('kpi-recettes-mois', fmt(d.recettes.total_mois));

    // Rappels urgents
    setText('kpi-rappels-urgents', d.rappels.nb_urgents);

  } catch (e) {
    console.error('Dashboard error:', e);
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ══════════════════════════════════════════════════════════════════════════════
//  FACTURES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerFacturesAPayer(dateDebut = '', dateFin = '') {
  const rows = await api('get_factures_a_payer', dateDebut, dateFin);
  const tbody = document.querySelector('#tbl-a tbody');
  if (!tbody) return;

  tbody.innerHTML = rows.length === 0
    ? `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:32px">Aucune facture en attente</td></tr>`
    : rows.map(f => `
      <tr data-id="${f.id}">
        <td>${f.numero}</td>
        <td class="mono">${f.fournisseur}</td>
        <td class="amt">${fmt(f.montant)}</td>
        <td>${fmtDate(f.date_echeance)}</td>
        <td>${f.commentaire || '—'}</td>
        <td>${badge(f.statut)}</td>
        <td>
          <button class="btn btn-primary btn-sm"
            onclick="ouvrirModalPayer(${f.id}, '${f.fournisseur}', ${f.montant})">
            Marquer payée
          </button>
          <button class="btn btn-ghost btn-sm" style="margin-left:4px"
            onclick="supprimerFacture(${f.id})">Suppr.</button>
        </td>
      </tr>`).join('');
}

async function chargerFacturesPayees(dateDebut = '', dateFin = '') {
  const rows = await api('get_factures_payees', dateDebut, dateFin);
  const tbody = document.querySelector('#tbl-p tbody');
  if (!tbody) return;

  tbody.innerHTML = rows.length === 0
    ? `<tr><td colspan="9" style="text-align:center;color:var(--text3);padding:32px">Aucune facture payée</td></tr>`
    : rows.map(f => `
      <tr data-id="${f.id}">
        <td>${f.fournisseur}</td>
        <td class="mono">${f.numero}</td>
        <td class="amt">${fmt(f.montant)}</td>
        <td>${fmtDate(f.date_echeance)}</td>
        <td>${fmtDate(f.date_paiement)}</td>
        <td class="mono">${f.ref_transaction || '—'}</td>
        <td>${f.mode_reglement === 'virement' ? 'Virement' : 'Espèces'}</td>
        <td>${f.commentaire || '—'}</td>
        <td><button class="btn btn-ghost btn-sm"
          onclick="supprimerFacture(${f.id})">Suppr.</button></td>
      </tr>`).join('');
}

async function filtrerFactures() {
  const debut = document.getElementById('f-date-debut')?.value || '';
  const fin   = document.getElementById('f-date-fin')?.value   || '';
  await chargerFacturesAPayer(debut, fin);
  await chargerFacturesPayees(debut, fin);
}

async function reinitFiltreFactures() {
  const d = document.getElementById('f-date-debut');
  const f = document.getElementById('f-date-fin');
  if (d) d.value = '';
  if (f) f.value = '';
  await chargerFacturesAPayer();
  await chargerFacturesPayees();
}

function ouvrirModalPayer(id, fournisseur, montant) {
  document.getElementById('modal-title').textContent =
    `Marquer comme payée — ${fournisseur} (${fmt(montant)})`;
  document.getElementById('modal-facture-id').value = id;
  document.getElementById('overlay').classList.add('show');
  document.getElementById('modal-mode').style.display = 'block';
}

async function enregistrerPaiement() {
  const id   = document.getElementById('modal-facture-id')?.value;
  const ref  = document.getElementById('modal-ref')?.value?.trim();
  const mode = document.getElementById('modal-mode-select')?.value;
  const date = document.getElementById('modal-date-paiement')?.value;

  if (!ref)  { showNotif('Référence de transaction requise', 'error'); return; }
  if (!mode) { showNotif('Mode de règlement requis', 'error'); return; }

  try {
    await api('marquer_facture_payee', id, ref, mode, date || '');
    closeModal();
    showNotif('Facture marquée comme payée');
    await chargerFacturesAPayer();
    await chargerFacturesPayees();
    await chargerDashboard();
  } catch (e) {
    showNotif(e.message, 'error');
  }
}

async function soumettreNouvelleFacture() {
  const get = id => document.getElementById(id)?.value?.trim() || '';
  const numero      = get('modal-numero');
  const fournisseur = get('modal-fournisseur');
  const montant     = parseFloat(get('modal-montant').replace(',', '.'));
  const echeance    = get('modal-echeance');
  const commentaire = get('modal-commentaire');
  const budgetId    = null;

  if (!numero || !fournisseur || !echeance || isNaN(montant)) {
    showNotif('Veuillez remplir tous les champs obligatoires', 'error');
    return;
  }

  try {
    await api('ajouter_facture', numero, fournisseur, montant,
              echeance, commentaire, budgetId);
    closeModal();
    showNotif('Facture ajoutée');
    await chargerFacturesAPayer();
    await chargerDashboard();
  } catch (e) {
    showNotif(e.message, 'error');
  }
}

async function supprimerFacture(id) {
  if (!confirm('Supprimer cette facture ?')) return;
  try {
    await api('supprimer_facture', id);
    showNotif('Facture supprimée');
    await chargerFacturesAPayer();
    await chargerFacturesPayees();
    await chargerDashboard();
  } catch (e) {
    showNotif(e.message, 'error');
  }
}

async function exporterFactures() {
  try {
    const res = await api('exporter_factures');
    await api('ouvrir_fichier', res.chemin);
    showNotif('Export Excel ouvert');
  } catch (e) {
    showNotif(e.message, 'error');
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  VIREMENTS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerVirements(dateDebut = '', dateFin = '') {
  const rows  = await api('get_virements', dateDebut, dateFin);
  const tbody = document.querySelector('#tbl-virements tbody');
  if (!tbody) return;

  tbody.innerHTML = rows.length === 0
    ? `<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:32px">Aucun virement</td></tr>`
    : rows.map(v => `
      <tr>
        <td>${fmtDate(v.date_virement)}</td>
        <td>${v.beneficiaire}</td>
        <td class="amt neg">${fmt(v.montant)}</td>
        <td class="mono">${v.ref_transaction || '—'}</td>
        <td>${v.commentaire || '—'}</td>
        <td><button class="btn btn-ghost btn-sm"
          onclick="supprimerVirement(${v.id})">Suppr.</button></td>
      </tr>`).join('');
}

async function supprimerVirement(id) {
  if (!confirm('Supprimer ce virement ?')) return;
  try {
    await api('supprimer_virement', id);
    showNotif('Virement supprimé');
    await chargerVirements();
  } catch (e) { showNotif(e.message, 'error'); }
}

async function exporterVirements() {
  try {
    const res = await api('exporter_virements');
    await api('ouvrir_fichier', res.chemin);
  } catch (e) { showNotif(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  PETITE CAISSE
// ══════════════════════════════════════════════════════════════════════════════

async function chargerCaisse(dateDebut = '', dateFin = '') {
  const [ops, soldeData] = await Promise.all([
    api('get_operations_caisse', dateDebut, dateFin),
    api('get_solde_caisse')
  ]);

  // Solde temps réel
  const el = document.getElementById('solde-caisse');
  if (el) el.textContent = fmt(soldeData.solde);

  const tbody = document.querySelector('#tbl-caisse tbody');
  if (!tbody) return;

  tbody.innerHTML = ops.length === 0
    ? `<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:32px">Aucune opération</td></tr>`
    : ops.map(o => `
      <tr>
        <td>${fmtDate(o.date_operation)}</td>
        <td>${o.description}</td>
        <td>${o.categorie}</td>
        <td>${badge(o.type_operation === 'entree' ? 'ok' : 'en_attente')}</td>
        <td class="amt ${o.type_operation === 'entree' ? 'pos' : 'neg'}">
          ${o.type_operation === 'sortie' ? '-' : '+'}${fmt(o.montant)}
        </td>
        <td class="mono">${fmt(o.solde_apres)}</td>
        <td>${o.justificatif || '—'}</td>
        <td><button class="btn btn-ghost btn-sm"
          onclick="supprimerOperationCaisse(${o.id})">Suppr.</button></td>
      </tr>`).join('');
}

async function supprimerOperationCaisse(id) {
  if (!confirm('Supprimer cette opération ?')) return;
  try {
    await api('supprimer_operation_caisse', id);
    showNotif('Opération supprimée');
    await chargerCaisse();
  } catch (e) { showNotif(e.message, 'error'); }
}

async function rapprocher() {
  const val = parseFloat(document.getElementById('montant-physique')?.value);
  if (isNaN(val)) { showNotif('Entrez un montant physique', 'error'); return; }
  try {
    const r = await api('rapprocher_caisse', val);
    const msg = r.statut === 'ok'
      ? 'Caisse équilibrée — aucun écart.'
      : `Écart détecté : ${fmt(r.ecart)} (${r.statut})`;
    showNotif(msg, r.statut === 'ok' ? 'success' : 'warning');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function exporterCaisse() {
  try {
    const res = await api('exporter_caisse');
    await api('ouvrir_fichier', res.chemin);
  } catch (e) { showNotif(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  RECETTES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerRecettes(dateDebut = '', dateFin = '') {
  const rows  = await api('get_recettes', dateDebut, dateFin);
  const tbody = document.querySelector('#tbl-recettes tbody');
  if (!tbody) return;

  tbody.innerHTML = rows.length === 0
    ? `<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:32px">Aucune recette</td></tr>`
    : rows.map(r => `
      <tr>
        <td>${fmtDate(r.date_reception)}</td>
        <td>${r.nom_payeur}</td>
        <td class="mono">${r.numero_facture || '—'}</td>
        <td class="mono">${r.ref_transaction || '—'}</td>
        <td class="amt pos">${fmt(r.montant)}</td>
        <td><button class="btn btn-ghost btn-sm"
          onclick="supprimerRecette(${r.id})">Suppr.</button></td>
      </tr>`).join('');
}

async function supprimerRecette(id) {
  if (!confirm('Supprimer cette recette ?')) return;
  try {
    await api('supprimer_recette', id);
    showNotif('Recette supprimée');
    await chargerRecettes();
    await chargerDashboard();
  } catch (e) { showNotif(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  BUDGETS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerBudgets() {
  const budgets = await api('get_budgets');
  const tbody   = document.querySelector('#tbl-budgets tbody');
  if (!tbody) return;

  tbody.innerHTML = budgets.length === 0
    ? `<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:32px">Aucun budget</td></tr>`
    : budgets.map(b => `
      <tr>
        <td class="name">${b.nom}</td>
        <td class="mono">${fmt(b.montant_alloue)}</td>
        <td class="amt neg">${fmt(b.montant_consomme)}</td>
        <td class="mono" style="color:var(--purple)">${fmt(b.solde_restant < 0 ? 0 : 0)}</td>
        <td class="amt ${b.solde_restant < 0 ? 'neg' : 'pos'}">${fmt(b.solde_restant)}</td>
        <td>
          <div class="progress-track">
            <div class="progress-fill ${b.statut === 'critique' ? 'r' : b.statut === 'attention' ? 'o' : 'g'}"
                 style="width:${Math.min(b.progression_pct, 100)}%"></div>
          </div>
          <div class="pct">${b.progression_pct}%</div>
        </td>
        <td>${badge(b.statut)}</td>
        <td><button class="btn btn-ghost btn-sm"
          onclick="supprimerBudget(${b.id})">Suppr.</button></td>
      </tr>`).join('');
}

async function supprimerBudget(id) {
  if (!confirm('Supprimer ce budget ? Les dépenses liées seront dissociées.')) return;
  try {
    await api('supprimer_budget', id);
    showNotif('Budget supprimé');
    await chargerBudgets();
    await remplirSelectBudgets();
  } catch (e) { showNotif(e.message, 'error'); }
}

async function remplirSelectBudgets() {
  const budgets = await api('get_budgets_select');
  document.querySelectorAll('.select-budget').forEach(sel => {
    const val = sel.value;
    sel.innerHTML = '<option value="">— Aucun —</option>' +
      budgets.map(b => `<option value="${b.id}">${b.nom}</option>`).join('');
    sel.value = val;
  });
}

// ══════════════════════════════════════════════════════════════════════════════
//  RAPPELS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerRappels() {
  const rows     = await api('get_rappels');
  const container = document.getElementById('liste-rappels');
  if (!container) return;

  container.innerHTML = rows.length === 0
    ? `<div style="text-align:center;color:var(--text3);padding:32px">Aucun rappel configuré</div>`
    : rows.map(r => `
      <div class="rem-card">
        <div class="rem-line" style="background:${
          r.urgence === 'urgent'  ? 'var(--red)' :
          r.urgence === 'bientot' ? 'var(--orange)' : 'var(--border2)'}">
        </div>
        <div class="rem-body">
          <div class="rem-name">${r.fournisseur}</div>
          <div class="rem-detail">
            Échéance le ${fmtDate(r.date_echeance)} · 
            ${r.jours_restants >= 0 ? `dans ${r.jours_restants} jour(s)` : `${Math.abs(r.jours_restants)} jour(s) de retard`} · 
            ${r.email_dest}
          </div>
        </div>
        <div class="rem-amount">${fmt(r.montant)}</div>
        ${badge(r.urgence)}
        <button class="btn btn-ghost btn-sm" style="margin:0 4px"
          onclick="envoyerRappelManuel(${r.id})">✉ Envoyer</button>
        <button class="ra-btn del" style="margin-left:4px"
          onclick="supprimerRappel(${r.id})">Suppr.</button>
      </div>`).join('');
}

async function envoyerRappelManuel(id) {
  try {
    await api('envoyer_rappel_manuel', id);
    showNotif('Email de rappel envoyé');
    await chargerRappels();
  } catch (e) { showNotif(e.message, 'error'); }
}

async function supprimerRappel(id) {
  if (!confirm('Supprimer ce rappel ?')) return;
  try {
    await api('supprimer_rappel', id);
    showNotif('Rappel supprimé');
    await chargerRappels();
    await chargerDashboard();
  } catch (e) { showNotif(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  PARAMÈTRES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerConfig() {
  try {
    const cfg = await api('get_config');
    const map = {
      'smtp_host':           'cfg-smtp-host',
      'smtp_port':           'cfg-smtp-port',
      'smtp_user':           'cfg-smtp-user',
      'smtp_from':           'cfg-smtp-from',
      'email_destinataire':  'cfg-email-dest',
      'rappel_jours':        'cfg-rappel-jours',
      'seuil_alerte_caisse': 'cfg-seuil-caisse',
      'backup_directory':    'cfg-backup-dir',
    };
    for (const [key, elId] of Object.entries(map)) {
      const el = document.getElementById(elId);
      if (el && cfg[key]) el.value = cfg[key];
    }
  } catch (e) { console.error('chargerConfig:', e); }
}

async function sauvegarderConfig() {
  const get = id => document.getElementById(id)?.value?.trim() || '';
  const cfg = {
    smtp_host:           get('cfg-smtp-host'),
    smtp_port:           get('cfg-smtp-port'),
    smtp_user:           get('cfg-smtp-user'),
    smtp_from:           get('cfg-smtp-from'),
    email_destinataire:  get('cfg-email-dest'),
    rappel_jours:        get('cfg-rappel-jours'),
    seuil_alerte_caisse: get('cfg-seuil-caisse'),
    backup_directory:    get('cfg-backup-dir'),
  };

  // Mot de passe SMTP séparé
  const smtpPwd = document.getElementById('cfg-smtp-pass')?.value;
  if (smtpPwd) cfg.smtp_password = smtpPwd;

  try {
    await api('sauvegarder_config', cfg);
    showNotif('Configuration sauvegardée');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function testerSmtp() {
  try {
    const res = await api('tester_smtp');
    if (res.ok) showNotif('SMTP opérationnel — email de test envoyé');
    else        showNotif(`Erreur SMTP : ${res.erreur}`, 'error');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function changerMotDePasse() {
  const ancien  = document.getElementById('cfg-mdp-ancien')?.value;
  const nouveau = document.getElementById('cfg-mdp-nouveau')?.value;
  const confirm2 = document.getElementById('cfg-mdp-confirm')?.value;
  if (nouveau !== confirm2) { showNotif('Les mots de passe ne correspondent pas', 'error'); return; }
  try {
    await api('changer_password', ancien, nouveau);
    showNotif('Mot de passe mis à jour');
    document.getElementById('cfg-mdp-ancien').value  = '';
    document.getElementById('cfg-mdp-nouveau').value = '';
    document.getElementById('cfg-mdp-confirm').value = '';
  } catch (e) { showNotif(e.message, 'error'); }
}

async function exporterConfig() {
  try {
    const path = prompt('Chemin de destination (ex: C:\\backup\\config.db)');
    if (!path) return;
    await api('exporter_config', path);
    showNotif('Configuration exportée');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function importerConfig() {
  const mode = confirm('Écraser la configuration actuelle ?\nOK = Écraser | Annuler = Fusionner')
    ? 'ecraser' : 'fusionner';
  const path = prompt('Chemin du fichier à importer');
  if (!path) return;
  try {
    await api('importer_config', path, mode);
    showNotif('Configuration importée — redémarrez l\'application');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function envoyerBackupEmail() {
  try {
    await api('envoyer_backup_email');
    showNotif('Backup envoyé par email');
  } catch (e) { showNotif(e.message, 'error'); }
}

async function genererRapport(format = 'excel') {
  const debut = prompt('Date de début (YYYY-MM-DD)', new Date().getFullYear() + '-01-01');
  const fin   = prompt('Date de fin (YYYY-MM-DD)',   new Date().toISOString().split('T')[0]);
  if (!debut || !fin) return;
  try {
    const res = await api('generer_rapport', debut, fin, format);
    await api('ouvrir_fichier', res.chemin);
    showNotif('Rapport généré et ouvert');
  } catch (e) { showNotif(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  NAVIGATION — hook sur la fonction go() existante de la maquette
// ══════════════════════════════════════════════════════════════════════════════

const _goOriginal = window.go;
window.go = async function(el, name) {
  _goOriginal(el, name);
  switch(name) {
    case 'dashboard':  await chargerDashboard();               break;
    case 'factures':
      await chargerFacturesAPayer();
      await chargerFacturesPayees();
      break;
    case 'virements':  await chargerVirements();               break;
    case 'pettycash':  await chargerCaisse();                  break;
    case 'recettes':   await chargerRecettes();                break;
    case 'budgets':    await chargerBudgets();                 break;
    case 'rappels':    await chargerRappels();                 break;
    case 'settings':   await chargerConfig();                  break;
  }
};

// ══════════════════════════════════════════════════════════════════════════════
//  TOAST CSS (injecté dynamiquement)
// ══════════════════════════════════════════════════════════════════════════════

const toastStyle = document.createElement('style');
toastStyle.textContent = `
  .toast {
    position: fixed; bottom: 24px; right: 24px;
    padding: 12px 20px; border-radius: 8px;
    font-size: 13.5px; font-weight: 500;
    background: #0f0f0e; color: #fff;
    opacity: 0; transform: translateY(8px);
    transition: all .25s; z-index: 9999;
    max-width: 360px; pointer-events: none;
  }
  .toast.show { opacity: 1; transform: translateY(0); }
  .toast.toast-error   { background: #a31b1b; }
  .toast.toast-warning { background: #8a4a00; }
  .toast.toast-info    { background: #1a3a6b; }
  .toast.toast-success { background: #0a6640; }
`;
document.head.appendChild(toastStyle);
