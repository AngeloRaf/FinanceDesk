/**
 * FinanceDesk v1.1 — app.js
 * Bridge JS ↔ Python via window.pywebview.api
 */

'use strict';

// ── Utilitaires ───────────────────────────────────────────────────────────────

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
  return new Intl.NumberFormat('fr-FR', { style:'currency', currency:'EUR' }).format(montant ?? 0);
}
function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('fr-FR'); } catch { return iso; }
}
function badge(statut) {
  const map = {
    'en_attente': ['badge-orange','En attente'], 'payee': ['badge-green','Payée'],
    'actif':['badge-blue','Actif'], 'envoye':['badge-green','Envoyé'],
    'desactive':['badge-neutral','Désactivé'], 'ok':['badge-green','OK'],
    'attention':['badge-orange','Attention'], 'critique':['badge-red','Critique'],
    'urgent':['badge-red','Urgent'], 'bientot':['badge-orange','Bientôt'],
    'normal':['badge-neutral','En attente'], 'retard':['badge-red','En retard'],
    'entree':['badge-green','Entrée'], 'sortie':['badge-red','Sortie'],
  };
  const [cls, label] = map[statut] || ['badge-neutral', statut];
  return `<span class="badge ${cls}">${label}</span>`;
}
function showNotif(msg, type='success') {
  const n = document.createElement('div');
  n.className = `toast toast-${type}`;
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.classList.add('show'), 10);
  setTimeout(() => { n.classList.remove('show'); setTimeout(() => n.remove(), 300); }, 3500);
}
function $(id) { return document.getElementById(id); }
function val(id) { return $(id)?.value?.trim() || ''; }

// ── Démarrage ─────────────────────────────────────────────────────────────────

window.addEventListener('pywebviewready', async () => {
  try {
    const info = await api('demarrage');
    if (info.alerte_caisse) showNotif(`⚠ Solde caisse bas : ${fmt(info.solde_caisse)}`, 'warning');
    if (info.rappels_envoyes > 0) showNotif(`${info.rappels_envoyes} rappel(s) envoyé(s)`, 'info');
    await chargerDashboard();
  } catch(e) { console.error('Démarrage:', e); }
});

// ══════════════════════════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════════════════════════

const _goOriginal = window.go;
window.go = async function(el, name) {
  _goOriginal(el, name);
  try {
    switch(name) {
      case 'dashboard': await chargerDashboard(); break;
      case 'factures':  await chargerFacturesAPayer(); await chargerFacturesPayees(); break;
      case 'virements': await chargerVirements(); break;
      case 'pettycash': await chargerCaisse(); break;
      case 'recettes':  await chargerRecettes(); break;
      case 'budgets':   await chargerBudgets(); break;
      case 'rappels':   await chargerRappels(); break;
      case 'settings':  await chargerConfig(); break;
    }
  } catch(e) { console.error('Navigation:', e); }
};

// ══════════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

async function chargerDashboard() {
  try {
    const d = await api('get_dashboard');
    setText('kpi-a-payer',       fmt(d.factures.total_a_payer));
    setText('kpi-recettes-mois', fmt(d.recettes.total_mois));
    setText('kpi-solde-caisse',  fmt(d.caisse.solde));
    setText('kpi-rappels-urgents', d.rappels.nb_urgents);
  } catch(e) { console.error('Dashboard:', e); }
}
function setText(id, val) { const el=$(id); if(el) el.textContent=val; }

// ══════════════════════════════════════════════════════════════════════════════
//  FACTURES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerFacturesAPayer(deb='', fin='') {
  try {
    const rows = await api('get_factures_a_payer', deb, fin);
    const tbody = $('tbody-a');
    if (!tbody) return;
    tbody.innerHTML = rows.length === 0
      ? `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:32px">Aucune facture en attente</td></tr>`
      : rows.map(f => `<tr>
          <td class="mono">${f.numero}</td>
          <td class="name">${f.fournisseur}</td>
          <td class="amt neg">${fmt(f.montant)}</td>
          <td class="mono">${fmtDate(f.date_echeance)}</td>
          <td class="muted">${f.commentaire||'—'}</td>
          <td>${badge(f.statut)}</td>
          <td><div class="ra">
            <button class="ra-btn pay" onclick="ouvrirModalPayer(${f.id},'${f.fournisseur.replace(/'/g,"\\'")}',${f.montant})">✓ Payer</button>
            <button class="ra-btn del" onclick="supprimerFacture(${f.id})">Suppr.</button>
          </div></td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

async function chargerFacturesPayees(deb='', fin='') {
  try {
    const rows = await api('get_factures_payees', deb, fin);
    const tbody = $('tbody-p');
    if (!tbody) return;
    tbody.innerHTML = rows.length === 0
      ? `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:32px">Aucune facture payée</td></tr>`
      : rows.map(f => `<tr>
          <td class="mono">${f.numero}</td>
          <td class="name">${f.fournisseur}</td>
          <td class="amt neg">${fmt(f.montant)}</td>
          <td class="mono">${fmtDate(f.date_paiement)}</td>
          <td>${f.mode_reglement==='virement'?'<span class="badge badge-blue">Virement</span>':'<span class="badge badge-purple">Espèces</span>'}</td>
          <td class="ref">${f.ref_transaction||'—'}</td>
          <td class="muted">${f.commentaire||'—'}</td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

async function filtrerFactures() {
  await chargerFacturesAPayer(val('f-date-debut'), val('f-date-fin'));
  await chargerFacturesPayees(val('f-date-debut'), val('f-date-fin'));
}
async function reinitFiltreFactures() {
  if($('f-date-debut')) $('f-date-debut').value='';
  if($('f-date-fin'))   $('f-date-fin').value='';
  await chargerFacturesAPayer(); await chargerFacturesPayees();
}

function ouvrirModalPayer(id, fournisseur, montant) {
  $('modal-title').textContent = `Payer — ${fournisseur} (${fmt(montant)})`;
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <input type="hidden" id="modal-facture-id" value="${id}">
      <div class="fl form-full"><label>Référence de transaction</label>
        <input class="fi" id="modal-ref" placeholder="VIR-2025-XXXX"></div>
      <div class="fl"><label>Mode de règlement</label>
        <select class="fi" id="modal-mode-select">
          <option value="virement">Virement bancaire</option>
          <option value="especes">Espèces / Petite caisse</option>
        </select></div>
      <div class="fl"><label>Date de paiement</label>
        <input class="fi" type="date" id="modal-date-paiement" value="${new Date().toISOString().split('T')[0]}"></div>
    </div>`;
  $('modal-submit-btn').onclick = enregistrerPaiement;
  $('modal-submit-btn').textContent = 'Confirmer le paiement';
  $('overlay').classList.add('show');
}

async function enregistrerPaiement() {
  const id   = val('modal-facture-id');
  const ref  = val('modal-ref');
  const mode = $('modal-mode-select')?.value;
  const date = val('modal-date-paiement');
  if (!ref) { showNotif('Référence requise','error'); return; }
  try {
    await api('marquer_facture_payee', id, ref, mode, date);
    closeModal();
    showNotif('Facture marquée comme payée ✓');
    await chargerFacturesAPayer(); await chargerFacturesPayees(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}

function ouvrirModalNouvelleFacture() {
  $('modal-title').textContent = 'Ajouter une facture';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>N° Facture</label><input class="fi" id="modal-numero" placeholder="FAC-2025-XXXX"></div>
      <div class="fl"><label>Fournisseur</label><input class="fi" id="modal-fournisseur" placeholder="Nom"></div>
      <div class="fl"><label>Montant (€)</label><input class="fi" id="modal-montant" placeholder="0.00"></div>
      <div class="fl"><label>Date d'échéance</label><input class="fi" type="date" id="modal-echeance"></div>
      <div class="fl form-full"><label>Commentaire</label>
        <input class="fi" id="modal-commentaire" placeholder="Description optionnelle…"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreNouvelleFacture;
  $('modal-submit-btn').textContent = 'Enregistrer';
  $('overlay').classList.add('show');
}

async function soumettreNouvelleFacture() {
  const numero = val('modal-numero'), fournisseur = val('modal-fournisseur');
  const montant = parseFloat(val('modal-montant').replace(',','.'));
  const echeance = val('modal-echeance'), commentaire = val('modal-commentaire');
  if (!numero||!fournisseur||!echeance||isNaN(montant)) {
    showNotif('Veuillez remplir tous les champs obligatoires','error'); return;
  }
  try {
    await api('ajouter_facture', numero, fournisseur, montant, echeance, commentaire, null);
    closeModal(); showNotif('Facture ajoutée ✓');
    await chargerFacturesAPayer(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}

async function supprimerFacture(id) {
  if (!confirm('Supprimer cette facture ?')) return;
  try {
    await api('supprimer_facture', id);
    showNotif('Facture supprimée');
    await chargerFacturesAPayer(); await chargerFacturesPayees(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}
async function exporterFactures() {
  try { const r=await api('exporter_factures'); await api('ouvrir_fichier',r.chemin); showNotif('Export Excel ouvert'); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  VIREMENTS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerVirements(deb='', fin='') {
  try {
    const rows = await api('get_virements', deb, fin);
    const tbody = $('tbody-virements');
    if (!tbody) return;
    tbody.innerHTML = rows.length === 0
      ? `<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:32px">Aucun virement</td></tr>`
      : rows.map(v => `<tr>
          <td class="mono">${fmtDate(v.date_virement)}</td>
          <td class="name">${v.beneficiaire}</td>
          <td class="amt neg">${fmt(v.montant)}</td>
          <td class="ref">${v.ref_transaction||'—'}</td>
          <td class="muted">${v.commentaire||'—'}</td>
          <td><button class="ra-btn del" onclick="supprimerVirement(${v.id})">Suppr.</button></td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

async function filtrerVirements() {
  await chargerVirements(val('v-date-debut'), val('v-date-fin'));
}

function ouvrirModalVirement() {
  $('modal-title').textContent = 'Ajouter un virement';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>Bénéficiaire</label><input class="fi" id="v-beneficiaire" placeholder="Nom"></div>
      <div class="fl"><label>Montant (€)</label><input class="fi" id="v-montant" placeholder="0.00"></div>
      <div class="fl"><label>Date</label><input class="fi" type="date" id="v-date" value="${new Date().toISOString().split('T')[0]}"></div>
      <div class="fl"><label>Référence transaction</label><input class="fi" id="v-ref" placeholder="VIR-XXXX"></div>
      <div class="fl form-full"><label>Commentaire (N° facture)</label>
        <input class="fi" id="v-commentaire" placeholder="FAC-2025-XXXX"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreVirement;
  $('modal-submit-btn').textContent = 'Enregistrer';
  $('overlay').classList.add('show');
}

async function soumettreVirement() {
  const benef = val('v-beneficiaire'), montant = parseFloat(val('v-montant').replace(',','.'));
  const date = val('v-date'), ref = val('v-ref'), com = val('v-commentaire');
  if (!benef||!date||isNaN(montant)) { showNotif('Champs obligatoires manquants','error'); return; }
  try {
    await api('ajouter_virement', date, benef, montant, ref, com, null);
    closeModal(); showNotif('Virement ajouté ✓');
    await chargerVirements(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}

async function supprimerVirement(id) {
  if (!confirm('Supprimer ce virement ?')) return;
  try { await api('supprimer_virement', id); showNotif('Supprimé'); await chargerVirements(); }
  catch(e) { showNotif(e.message,'error'); }
}
async function exporterVirements() {
  try { const r=await api('exporter_virements'); await api('ouvrir_fichier',r.chemin); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  PETITE CAISSE
// ══════════════════════════════════════════════════════════════════════════════

async function chargerCaisse(deb='', fin='') {
  try {
    const [ops, soldeData] = await Promise.all([
      api('get_operations_caisse', deb, fin),
      api('get_solde_caisse')
    ]);
    const el=$('solde-caisse');
    if(el) el.textContent = fmt(soldeData.solde);
    const tbody=$('tbody-caisse');
    if (!tbody) return;
    tbody.innerHTML = ops.length === 0
      ? `<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:32px">Aucune opération</td></tr>`
      : ops.map(o => `<tr>
          <td class="mono">${fmtDate(o.date_operation)}</td>
          <td class="name">${o.description}</td>
          <td class="muted">${o.categorie}</td>
          <td>${badge(o.type_operation)}</td>
          <td class="amt ${o.type_operation==='entree'?'pos':'neg'}">${o.type_operation==='sortie'?'-':'+'}${fmt(o.montant)}</td>
          <td class="mono" style="color:var(--purple)">${fmt(o.solde_apres)}</td>
          <td class="ref">${o.justificatif||'—'}</td>
          <td><button class="ra-btn del" onclick="supprimerOperationCaisse(${o.id})">Suppr.</button></td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

async function filtrerCaisse() { await chargerCaisse(val('c-date-debut'), val('c-date-fin')); }

function ouvrirModalCaisse() {
  $('modal-title').textContent = 'Nouvelle opération caisse';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>Date</label><input class="fi" type="date" id="ca-date" value="${new Date().toISOString().split('T')[0]}"></div>
      <div class="fl"><label>Type</label>
        <select class="fi" id="ca-type">
          <option value="sortie">Sortie</option>
          <option value="entree">Entrée / Réappro</option>
        </select></div>
      <div class="fl form-full"><label>Description</label><input class="fi" id="ca-desc" placeholder="Description..."></div>
      <div class="fl"><label>Catégorie</label>
        <select class="fi" id="ca-cat">
          <option>Fournitures</option><option>Transport</option><option>Repas</option>
          <option>Remboursement employé</option><option>Réapprovisionnement caisse</option><option>Divers</option>
        </select></div>
      <div class="fl"><label>Montant (€)</label><input class="fi" id="ca-montant" placeholder="0.00"></div>
      <div class="fl form-full"><label>Justificatif (N° reçu)</label><input class="fi" id="ca-justif" placeholder="REC-XXXX"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreCaisse;
  $('modal-submit-btn').textContent = 'Enregistrer';
  $('overlay').classList.add('show');
}

async function soumettreCaisse() {
  const date=val('ca-date'), type=$('ca-type')?.value;
  const desc=val('ca-desc'), cat=$('ca-cat')?.value;
  const montant=parseFloat(val('ca-montant').replace(',','.'));
  const justif=val('ca-justif');
  if (!date||!desc||isNaN(montant)) { showNotif('Champs obligatoires manquants','error'); return; }
  try {
    const r = await api('ajouter_operation_caisse', date, desc, cat, type, montant, justif, null);
    closeModal();
    showNotif(`Opération enregistrée. Solde : ${fmt(r.solde_apres)}${r.alerte?' ⚠ Seuil atteint':''}`);
    await chargerCaisse(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}

async function supprimerOperationCaisse(id) {
  if (!confirm('Supprimer cette opération ?')) return;
  try { await api('supprimer_operation_caisse', id); await chargerCaisse(); }
  catch(e) { showNotif(e.message,'error'); }
}

async function ouvrirRapprochement() {
  $('modal-title').textContent = 'Rapprochement de caisse';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl form-full"><label>Montant physiquement compté (€)</label>
        <input class="fi" id="montant-physique" placeholder="0.00" type="number" step="0.01"></div>
    </div>`;
  $('modal-submit-btn').onclick = async () => {
    const v = parseFloat($('montant-physique')?.value);
    if (isNaN(v)) { showNotif('Entrez un montant','error'); return; }
    try {
      const r = await api('rapprocher_caisse', v);
      closeModal();
      const msg = r.statut==='ok'
        ? 'Caisse équilibrée — aucun écart ✓'
        : `Écart : ${fmt(r.ecart)} (${r.statut}) | Théorique: ${fmt(r.solde_theorique)} | Compté: ${fmt(r.montant_physique)}`;
      showNotif(msg, r.statut==='ok'?'success':'warning');
    } catch(e) { showNotif(e.message,'error'); }
  };
  $('modal-submit-btn').textContent = 'Vérifier';
  $('overlay').classList.add('show');
}

async function exporterCaisse() {
  try { const r=await api('exporter_caisse'); await api('ouvrir_fichier',r.chemin); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  RECETTES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerRecettes(deb='', fin='') {
  try {
    const rows = await api('get_recettes', deb, fin);
    const tbody=$('tbody-recettes');
    if (!tbody) return;
    tbody.innerHTML = rows.length===0
      ? `<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:32px">Aucune recette</td></tr>`
      : rows.map(r => `<tr>
          <td class="mono">${fmtDate(r.date_reception)}</td>
          <td class="name">${r.nom_payeur}</td>
          <td class="amt pos">${fmt(r.montant)}</td>
          <td class="mono">${r.numero_facture||'—'}</td>
          <td class="ref">${r.ref_transaction||'—'}</td>
          <td><button class="ra-btn del" onclick="supprimerRecette(${r.id})">Suppr.</button></td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

async function filtrerRecettes() { await chargerRecettes(val('r-date-debut'), val('r-date-fin')); }

function ouvrirModalRecette() {
  $('modal-title').textContent = 'Ajouter une réception';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>Date</label><input class="fi" type="date" id="rec-date" value="${new Date().toISOString().split('T')[0]}"></div>
      <div class="fl"><label>Payeur / Nom</label><input class="fi" id="rec-payeur" placeholder="Nom du client"></div>
      <div class="fl"><label>Montant (€)</label><input class="fi" id="rec-montant" placeholder="0.00"></div>
      <div class="fl"><label>N° Facture (optionnel)</label><input class="fi" id="rec-facture" placeholder="FAC-CLI-XXXX"></div>
      <div class="fl form-full"><label>Référence transaction</label><input class="fi" id="rec-ref" placeholder="REC-XXXX"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreRecette;
  $('modal-submit-btn').textContent = 'Enregistrer';
  $('overlay').classList.add('show');
}

async function soumettreRecette() {
  const date=val('rec-date'), payeur=val('rec-payeur');
  const montant=parseFloat(val('rec-montant').replace(',','.'));
  const facture=val('rec-facture'), ref=val('rec-ref');
  if (!date||!payeur||isNaN(montant)) { showNotif('Champs obligatoires manquants','error'); return; }
  try {
    await api('ajouter_recette', date, payeur, montant, facture, ref, '');
    closeModal(); showNotif('Réception enregistrée ✓');
    await chargerRecettes(); await chargerDashboard();
  } catch(e) { showNotif(e.message,'error'); }
}

async function supprimerRecette(id) {
  if (!confirm('Supprimer ?')) return;
  try { await api('supprimer_recette', id); await chargerRecettes(); await chargerDashboard(); }
  catch(e) { showNotif(e.message,'error'); }
}
async function exporterRecettes() {
  try { const r=await api('exporter_recettes'); await api('ouvrir_fichier',r.chemin); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  BUDGETS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerBudgets() {
  try {
    const budgets = await api('get_budgets');
    const tbody=$('tbody-budgets');
    if (!tbody) return;
    tbody.innerHTML = budgets.length===0
      ? `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:32px">Aucun budget</td></tr>`
      : budgets.map(b => `<tr>
          <td class="name">${b.nom}</td>
          <td class="mono">${fmt(b.montant_alloue)}</td>
          <td class="amt neg">${fmt(b.montant_consomme)}</td>
          <td class="mono" style="color:var(--purple)">—</td>
          <td class="amt ${b.solde_restant<0?'neg':'pos'}">${fmt(b.solde_restant)}</td>
          <td><div class="progress-track"><div class="progress-fill ${b.statut==='critique'?'r':b.statut==='attention'?'o':'g'}" style="width:${Math.min(b.progression_pct,100)}%"></div></div><div class="pct">${b.progression_pct}%</div></td>
          <td>${badge(b.statut)}
            <button class="ra-btn del" style="margin-left:6px" onclick="supprimerBudget(${b.id})">Suppr.</button></td>
        </tr>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

function ouvrirModalBudget() {
  $('modal-title').textContent = 'Nouveau budget';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>Nom du budget</label><input class="fi" id="bud-nom" placeholder="Ex: Marketing"></div>
      <div class="fl"><label>Montant alloué (€)</label><input class="fi" id="bud-montant" placeholder="0.00"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreBudget;
  $('modal-submit-btn').textContent = 'Créer le budget';
  $('overlay').classList.add('show');
}

async function soumettreBudget() {
  const nom=val('bud-nom'), montant=parseFloat(val('bud-montant').replace(',','.'));
  if (!nom||isNaN(montant)) { showNotif('Champs obligatoires manquants','error'); return; }
  try {
    await api('ajouter_budget', nom, montant);
    closeModal(); showNotif('Budget créé ✓');
    await chargerBudgets();
  } catch(e) { showNotif(e.message,'error'); }
}

async function supprimerBudget(id) {
  if (!confirm('Supprimer ce budget ? Les dépenses liées seront dissociées.')) return;
  try { await api('supprimer_budget', id); await chargerBudgets(); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  RAPPELS
// ══════════════════════════════════════════════════════════════════════════════

async function chargerRappels() {
  try {
    const rows = await api('get_rappels');
    const container=$('liste-rappels');
    if (!container) return;
    container.innerHTML = rows.length===0
      ? `<div style="text-align:center;color:var(--text3);padding:32px">Aucun rappel configuré</div>`
      : rows.map(r => `
        <div class="rem-card">
          <div class="rem-line" style="background:${r.urgence==='urgent'?'var(--red)':r.urgence==='bientot'?'var(--orange)':'var(--border2)'}"></div>
          <div class="rem-body">
            <div class="rem-name">${r.fournisseur}</div>
            <div class="rem-detail">Échéance le ${fmtDate(r.date_echeance)} · ${r.jours_restants>=0?`dans ${r.jours_restants} jour(s)`:`${Math.abs(r.jours_restants)} jour(s) de retard`} · ${r.email_dest}</div>
          </div>
          <div class="rem-amount">${fmt(r.montant)}</div>
          ${badge(r.urgence)}
          <button class="btn btn-ghost btn-sm" style="margin:0 4px" onclick="envoyerRappelManuel(${r.id})">✉ Envoyer</button>
          <button class="ra-btn del" onclick="supprimerRappel(${r.id})">Suppr.</button>
        </div>`).join('');
  } catch(e) { showNotif(e.message,'error'); }
}

function ouvrirModalRappel() {
  $('modal-title').textContent = 'Nouveau rappel';
  $('modal-body').innerHTML = `
    <div class="form-grid">
      <div class="fl"><label>Fournisseur</label><input class="fi" id="rap-fourn" placeholder="Nom"></div>
      <div class="fl"><label>Montant (€)</label><input class="fi" id="rap-montant" placeholder="0.00"></div>
      <div class="fl"><label>Date d'échéance</label><input class="fi" type="date" id="rap-date"></div>
      <div class="fl"><label>Email destinataire</label><input class="fi" id="rap-email" placeholder="finance@exemple.com"></div>
    </div>`;
  $('modal-submit-btn').onclick = soumettreRappel;
  $('modal-submit-btn').textContent = 'Créer le rappel';
  $('overlay').classList.add('show');
}

async function soumettreRappel() {
  const fourn=val('rap-fourn'), montant=parseFloat(val('rap-montant').replace(',','.'));
  const date=val('rap-date'), email=val('rap-email');
  if (!fourn||!date||!email||isNaN(montant)) { showNotif('Champs obligatoires manquants','error'); return; }
  try {
    await api('ajouter_rappel', fourn, montant, date, email);
    closeModal(); showNotif('Rappel créé ✓');
    await chargerRappels();
  } catch(e) { showNotif(e.message,'error'); }
}

async function envoyerRappelManuel(id) {
  try { await api('envoyer_rappel_manuel', id); showNotif('Email envoyé ✓'); await chargerRappels(); }
  catch(e) { showNotif(e.message,'error'); }
}
async function supprimerRappel(id) {
  if (!confirm('Supprimer ce rappel ?')) return;
  try { await api('supprimer_rappel', id); await chargerRappels(); }
  catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  PARAMÈTRES
// ══════════════════════════════════════════════════════════════════════════════

async function chargerConfig() {
  try {
    const cfg = await api('get_config');
    const map = {
      'smtp_host':'cfg-smtp-host','smtp_port':'cfg-smtp-port',
      'smtp_user':'cfg-smtp-user','smtp_from':'cfg-smtp-from',
      'email_destinataire':'cfg-email-dest','rappel_jours':'cfg-rappel-jours',
      'seuil_alerte_caisse':'cfg-seuil-caisse','backup_directory':'cfg-backup-dir'
    };
    for (const [key,id] of Object.entries(map)) {
      const el=$(id); if(el && cfg[key]) el.value=cfg[key];
    }
  } catch(e) { console.error('chargerConfig:', e); }
}

async function sauvegarderConfig() {
  const cfg = {
    smtp_host:val('cfg-smtp-host'), smtp_port:val('cfg-smtp-port'),
    smtp_user:val('cfg-smtp-user'), smtp_from:val('cfg-smtp-from'),
    email_destinataire:val('cfg-email-dest'), rappel_jours:val('cfg-rappel-jours'),
    seuil_alerte_caisse:val('cfg-seuil-caisse'), backup_directory:val('cfg-backup-dir')
  };
  const pwd=$('cfg-smtp-pass')?.value;
  if(pwd) cfg.smtp_password=pwd;
  try { await api('sauvegarder_config', cfg); showNotif('Configuration sauvegardée ✓'); }
  catch(e) { showNotif(e.message,'error'); }
}

async function testerSmtp() {
  try {
    const r=await api('tester_smtp');
    if(r.ok) showNotif('SMTP opérationnel ✓');
    else showNotif(`Erreur SMTP : ${r.erreur}`,'error');
  } catch(e) { showNotif(e.message,'error'); }
}

async function changerMotDePasse() {
  const ancien=val('cfg-mdp-ancien'), nouveau=val('cfg-mdp-nouveau'), conf=val('cfg-mdp-confirm');
  if(nouveau!==conf) { showNotif('Les mots de passe ne correspondent pas','error'); return; }
  try { await api('changer_password', ancien, nouveau); showNotif('Mot de passe mis à jour ✓'); }
  catch(e) { showNotif(e.message,'error'); }
}

async function exporterConfig() {
  const path=prompt('Chemin de destination (ex: C:\\backup\\config.db)');
  if(!path) return;
  try { await api('exporter_config', path); showNotif('Configuration exportée ✓'); }
  catch(e) { showNotif(e.message,'error'); }
}

async function importerConfig() {
  const mode=confirm('Écraser la configuration ?\nOK = Écraser | Annuler = Fusionner')?'ecraser':'fusionner';
  const path=prompt('Chemin du fichier à importer');
  if(!path) return;
  try { await api('importer_config', path, mode); showNotif('Configuration importée — redémarrez'); }
  catch(e) { showNotif(e.message,'error'); }
}

async function envoyerBackupEmail() {
  try { await api('envoyer_backup_email'); showNotif('Backup envoyé par email ✓'); }
  catch(e) { showNotif(e.message,'error'); }
}

async function genererRapport(format='excel') {
  const debut=prompt('Date de début (YYYY-MM-DD)', new Date().getFullYear()+'-01-01');
  const fin=prompt('Date de fin (YYYY-MM-DD)', new Date().toISOString().split('T')[0]);
  if(!debut||!fin) return;
  try {
    const r=await api('generer_rapport', debut, fin, format);
    await api('ouvrir_fichier', r.chemin);
    showNotif('Rapport généré ✓');
  } catch(e) { showNotif(e.message,'error'); }
}

// ══════════════════════════════════════════════════════════════════════════════
//  TOAST CSS
// ══════════════════════════════════════════════════════════════════════════════

const toastStyle=document.createElement('style');
toastStyle.textContent=`
  .toast { position:fixed; bottom:24px; right:24px; padding:12px 20px; border-radius:8px;
    font-size:13.5px; font-weight:500; background:#0f0f0e; color:#fff;
    opacity:0; transform:translateY(8px); transition:all .25s; z-index:9999;
    max-width:400px; pointer-events:none; }
  .toast.show { opacity:1; transform:translateY(0); }
  .toast.toast-error { background:#a31b1b; }
  .toast.toast-warning { background:#8a4a00; }
  .toast.toast-info { background:#1a3a6b; }
  .toast.toast-success { background:#0a6640; }
`;
document.head.appendChild(toastStyle);