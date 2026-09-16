/**
 * FluxLab - Straznik zmarnowanego budzetu (Wasted-Spend Guardian)
 * Google Ads Script. Dziala W KONCIE KLIENTA.
 *
 * Co robi (uruchamiany nocnym harmonogramem):
 *  1. Przeglada raport wyszukiwanych hasel z ostatnich LOOKBACK_DAYS dni.
 *  2. Znajduje hasla z 0 konwersji i kosztem > COST_THRESHOLD.
 *  3. Dodaje je jako wykluczajace slowa kluczowe (dokladne dopasowanie)
 *     do wskazanej listy wykluczen ALEBO do kampanii.
 *  4. Wysyla e-mail z podsumowaniem: co dodano i ile budzetu to chronilo.
 *
 * BEZPIECZENSTWO: domyslnie DRY_RUN = true (nic nie zmienia, tylko raportuje mailem).
 * Ustaw DRY_RUN = false dopiero po weryfikacji pierwszego maila.
 *
 * Instrukcja wklejenia w README.md.
 */

// ====================== KONFIGURACJA ======================
var CONFIG = {
  DRY_RUN: true, // true = tylko raport mailem, false = realnie dodaje wykluczenia
  LOOKBACK_DAYS: 30, // okno analizy
  COST_THRESHOLD: 30.0, // prog kosztu (w walucie konta) dla frazy bez konwersji
  MIN_CLICKS: 3, // minimalna liczba klikniec
  EMAIL: "twoj-adres@example.com", // adres na alerty (ZMIEN)
  // Nazwa wspoldzielonej listy wykluczen. Jesli nie istnieje, skrypt ja utworzy.
  // Lista jest podpinana pod wszystkie kampanie w tej samej walucie.
  NEGATIVE_LIST_NAME: "FluxLab - Auto Wasted-Spend",
  MATCH_TYPE: "EXACT", // EXACT | PHRASE | BROAD dla dodawanych wykluczen
  LABEL: "[FluxLab]", // prefiks w temacie maila
};
// ==========================================================

function main() {
  var range = dateRange(CONFIG.LOOKBACK_DAYS);
  var query =
    "SELECT search_term_view.search_term, metrics.cost_micros, " +
    "metrics.clicks, metrics.conversions " +
    "FROM search_term_view " +
    "WHERE segments.date BETWEEN '" +
    range.from +
    "' AND '" +
    range.to +
    "' " +
    "AND metrics.conversions = 0 " +
    "AND metrics.clicks > " +
    CONFIG.MIN_CLICKS;

  var rows = AdsApp.report(query).rows();
  var wasted = [];
  var totalWasted = 0;

  while (rows.hasNext()) {
    var row = rows.next();
    var cost = Number(row["metrics.cost_micros"]) / 1e6;
    if (cost > CONFIG.COST_THRESHOLD) {
      wasted.push({
        term: row["search_term_view.search_term"],
        cost: cost,
        clicks: Number(row["metrics.clicks"]),
      });
      totalWasted += cost;
    }
  }

  wasted.sort(function (a, b) {
    return b.cost - a.cost;
  });

  var added = [];
  if (!CONFIG.DRY_RUN && wasted.length > 0) {
    var list = getOrCreateNegativeList(CONFIG.NEGATIVE_LIST_NAME);
    for (var i = 0; i < wasted.length; i++) {
      var neg = formatNegative(wasted[i].term, CONFIG.MATCH_TYPE);
      list.addNegativeKeyword(neg);
      added.push(neg);
    }
    attachListToCampaigns(list);
  }

  sendReport(wasted, totalWasted, added);
  Logger.log(
    "Znaleziono " +
      wasted.length +
      " fraz, koszt " +
      totalWasted.toFixed(2) +
      ". DRY_RUN=" +
      CONFIG.DRY_RUN,
  );
}

function dateRange(days) {
  var tz = AdsApp.currentAccount().getTimeZone();
  var to = new Date();
  var from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
  return {
    from: Utilities.formatDate(from, tz, "yyyy-MM-dd"),
    to: Utilities.formatDate(to, tz, "yyyy-MM-dd"),
  };
}

function formatNegative(term, matchType) {
  if (matchType === "EXACT") return "[" + term + "]";
  if (matchType === "PHRASE") return '"' + term + '"';
  return term;
}

function getOrCreateNegativeList(name) {
  var it = AdsApp.negativeKeywordLists()
    .withCondition("shared_set.name = '" + name + "'")
    .get();
  if (it.hasNext()) return it.next();
  return AdsApp.newNegativeKeywordListBuilder()
    .withName(name)
    .build()
    .getResult();
}

function attachListToCampaigns(list) {
  var camps = AdsApp.campaigns()
    .withCondition("campaign.status = ENABLED")
    .get();
  while (camps.hasNext()) {
    var c = camps.next();
    try {
      c.addNegativeKeywordList(list);
    } catch (e) {
      /* juz podpieta */
    }
  }
}

function sendReport(wasted, totalWasted, added) {
  var mode = CONFIG.DRY_RUN
    ? "PODGLAD (nic nie zmieniono)"
    : "ZASTOSOWANO wykluczenia";
  var acct =
    AdsApp.currentAccount().getName() ||
    AdsApp.currentAccount().getCustomerId();
  var subject =
    CONFIG.LABEL +
    " Straznik budzetu Ads: " +
    totalWasted.toFixed(2) +
    " ochronione (" +
    acct +
    ")";

  var lines = [];
  lines.push("Konto: " + acct);
  lines.push("Tryb: " + mode);
  lines.push("Okno: ostatnie " + CONFIG.LOOKBACK_DAYS + " dni");
  lines.push(
    "Prog: koszt > " +
      CONFIG.COST_THRESHOLD +
      ", klikniecia > " +
      CONFIG.MIN_CLICKS +
      ", 0 konwersji",
  );
  lines.push("");
  lines.push("Zmarnowany budzet wykryty: " + totalWasted.toFixed(2));
  lines.push("Fraz do wykluczenia: " + wasted.length);
  if (added.length > 0) lines.push("Dodane wykluczenia: " + added.length);
  lines.push("");
  lines.push("Top frazy:");
  for (var i = 0; i < Math.min(wasted.length, 20); i++) {
    lines.push(
      "  " +
        wasted[i].cost.toFixed(2) +
        "  (" +
        wasted[i].clicks +
        " klikn.)  " +
        wasted[i].term,
    );
  }
  if (CONFIG.DRY_RUN) {
    lines.push("");
    lines.push(
      "To byl tryb podgladu. Aby skrypt sam dodawal wykluczenia, ustaw DRY_RUN = false.",
    );
  }

  MailApp.sendEmail(CONFIG.EMAIL, subject, lines.join("\n"));
}
