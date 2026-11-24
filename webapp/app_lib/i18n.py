"""French / English labels and number formatting.

Usage: t("key") returns the label in the current language; fmt_* format numbers the way each
language writes them (FR 1 234,56 / EN 1,234.56). To add a label, add one line to LABELS.
"""

from __future__ import annotations

import datetime as dt
import math

import streamlit as st

LANGS = {"fr": "Français", "en": "English"}

LABELS: dict[str, tuple[str, str]] = {
    # app
    "app_title": ("Marché BRVM — analyse des données", "BRVM market — data analysis"),
    "language": ("Langue", "Language"),
    "data_as_of": ("Données au {date}", "Data as of {date}"),
    "footer": ("Source : Bulletins Officiels de la Cote de la BRVM, extraits automatiquement. Prix ajustés des "
               "fractionnements. Informations fournies à titre indicatif, sans garantie : ceci n'est pas un conseil "
               "en investissement.",
               "Source: BRVM Bulletins Officiels de la Cote, extracted automatically. Prices adjusted for splits. "
               "Information provided as is, without warranty: this is not investment advice."),
    "download_csv": ("Télécharger (CSV)", "Download (CSV)"),
    "no_data": ("Aucune donnée pour cette sélection.", "No data for this selection."),
    "period": ("Période", "Period"),
    "session": ("Séance", "Session"),
    # pages
    "page_overview": ("Vue du marché", "Market overview"),
    "page_stock": ("Fiche valeur", "Stock explorer"),
    "page_compare": ("Comparer & filtrer", "Compare & screen"),
    "page_bonds": ("Obligations", "Bonds"),
    "page_funds": ("OPCVM", "Mutual funds"),
    "page_bulletins": ("Bulletins officiels (BOC)", "Official bulletins (BOC)"),
    # performance basis (total return)
    "basis": ("Performance", "Performance"),
    "basis_tr": ("Dividendes réinvestis", "Dividends reinvested"),
    "basis_price": ("Cours seul", "Price only"),
    "basis_help": ("Dividendes réinvestis : le dividende net est réinvesti le jour de son détachement (rendement "
                   "total). Cours seul : variation du cours ajusté des fractionnements, sans les dividendes.",
                   "Dividends reinvested: the net dividend is reinvested on its ex-dividend day (total return). "
                   "Price only: change of the split-adjusted price, without dividends."),
    "basis_note_tr": ("Performance dividendes nets réinvestis le jour du détachement. Choix dans le menu de gauche.",
                      "Performance with net dividends reinvested on the ex-dividend day. Change it in the left menu."),
    "basis_note_price": ("Performance du cours seul, hors dividendes. Choix dans le menu de gauche.",
                         "Price-only performance, without dividends. Change it in the left menu."),
    "tr_price": ("Cours avec dividendes réinvestis", "Price with dividends reinvested"),
    "ytd_tr": ("Perf. annuelle (div. réinvestis)", "YTD (dividends reinvested)"),
    "return_1y_tr": ("Perf. 1 an (div. réinvestis)", "1-year (dividends reinvested)"),
    # daily briefing (app_lib/briefing.py)
    "briefing_title": ("Résumé de la séance", "Session summary"),
    "sum_up": ("Le BRVM Composite a progressé de {pct} à {value} points", "The BRVM Composite rose {pct} to {value} points"),
    "sum_down": ("Le BRVM Composite a reculé de {pct} à {value} points", "The BRVM Composite fell {pct} to {value} points"),
    "sum_flat": ("Le BRVM Composite est resté stable à {value} points", "The BRVM Composite was unchanged at {value} points"),
    "sum_b30": (" (BRVM 30 : {pct})", " (BRVM 30: {pct})"),
    "sum_ytd": ("Depuis le 1er janvier : {pct}.", "Year to date: {pct}."),
    "sum_breadth": ("{up}, {down}, {flat}.", "{up}, {down}, {flat}."),
    "n_up_one": ("1 valeur en hausse", "1 stock up"), "n_up_many": ("{n} valeurs en hausse", "{n} stocks up"),
    "n_down_one": ("1 en baisse", "1 down"), "n_down_many": ("{n} en baisse", "{n} down"),
    "n_flat_one": ("1 inchangée", "1 unchanged"), "n_flat_many": ("{n} inchangées", "{n} unchanged"),
    "sum_value": ("Valeur échangée sur les actions : {amount} FCFA", "Equity value traded: {amount} FCFA"),
    "sum_value_above": ("{pct} au-dessus de la moyenne des 3 derniers mois", "{pct} above its 3-month average"),
    "sum_value_below": ("{pct} en dessous de la moyenne des 3 derniers mois", "{pct} below its 3-month average"),
    "sum_top_share": ("{name} en représente {pct}.", "{name} accounted for {pct} of it."),
    "sum_best": ("plus forte hausse : {name} ({pct})", "top gainer: {name} ({pct})"),
    "sum_worst": ("plus forte baisse : {name} ({pct})", "top loser: {name} ({pct})"),
    "events_title": ("Faits marquants", "Highlights"),
    "ev_high": ("Plus hauts sur 52 semaines", "52-week highs"),
    "ev_low": ("Plus bas sur 52 semaines", "52-week lows"),
    "ev_limit": ("Proches de la limite journalière de ±7,5 %", "Close to the ±7.5% daily limit"),
    "ev_volume": ("Échanges inhabituels (≥ 5 × la moyenne de 3 mois)", "Unusual trading (≥ 5× the 3-month average)"),
    "ev_splits": ("Fractionnements", "Splits"),
    "ev_notices": ("Nouveaux avis et communiqués ({n})", "New notices and releases ({n})"),
    "ev_text": ("Texte", "Text"),
    "no_events": ("Aucun fait marquant pour cette séance.", "Nothing notable in this session."),
    "upcoming_title": ("À venir", "Upcoming"),
    "no_upcoming": ("Aucun événement annoncé.", "No event announced."),
    "event": ("Événement", "Event"), "company": ("Société", "Company"),
    "ev_dividend": ("Paiement de dividende : {amount} FCFA {net} par action", "Dividend payment: {amount} FCFA {net} per share"),
    "div_net": ("net", "net"), "div_gross": ("brut", "gross"),
    "ev_split": ("Fractionnement : {new} actions nouvelles pour {old} ancienne", "Split: {new} new shares for {old} old"),
    "ev_listing": ("Première cotation : {what}", "First listing: {what}"),
    "ev_meeting": ("Assemblée générale {nature}", "{nature} general meeting"),
    "cancelled": ("annulée", "cancelled"),
    "upcoming_note": ("Selon les bulletins publiés jusqu'à cette séance. 📄 : bulletin qui l'annonce.",
                      "As announced in the bulletins up to this session. 📄: the bulletin announcing it."),
    # official bulletins (links to brvm.org)
    "bulletins_intro": ("La BRVM publie chaque jour de bourse son Bulletin Officiel de la Cote (BOC). Les liens "
                        "ouvrent le PDF officiel sur brvm.org.",
                        "BRVM publishes its official price list, the Bulletin Officiel de la Cote (BOC), every "
                        "trading day. The links open the official PDF on brvm.org."),
    "boc": ("BOC", "BOC"), "boc_link": ("📄 BOC", "📄 BOC"),
    "open_boc": ("Ouvrir le BOC du {date}", "Open the BOC of {date}"),
    "previous_boc": ("Bulletin précédent : {date}", "Previous bulletin: {date}"),
    "boc_weekend": ("Pas de séance le week-end.", "No session at weekends."),
    "boc_none": ("Pas de bulletin le {date} : jour férié ou pas de séance.",
                 "No bulletin on {date}: holiday or no session."),
    "boc_unavailable": ("Le bulletin du {date} existe, mais son lien sur brvm.org est cassé.",
                        "The bulletin of {date} exists, but its link on brvm.org is broken."),
    "bulletin_list": ("Liste des bulletins", "List of bulletins"),
    "year": ("Année", "Year"), "month": ("Mois", "Month"), "all_months": ("Tous", "All"),
    "weekday": ("Jour", "Day"), "status": ("Statut", "Status"),
    "bst_published": ("Publié", "Published"),
    "bst_none": ("Pas de bulletin (férié, pas de séance)", "No bulletin (holiday, no session)"),
    "bst_unavailable": ("Lien cassé sur brvm.org", "Broken link on brvm.org"),
    "bulletins_count": ("{n} bulletins publiés, {m} jours sans bulletin", "{n} bulletins published, {m} days without a bulletin"),
    # periods
    "1M": ("1M", "1M"), "3M": ("3M", "3M"), "6M": ("6M", "6M"), "YTD": ("Début d'année", "YTD"),
    "1Y": ("1A", "1Y"), "3Y": ("3A", "3Y"), "5Y": ("5A", "5Y"), "ALL": ("Tout", "All"),
    # overview
    "day": ("jour", "day"), "ytd": ("depuis le 1er janv.", "YTD"),
    "equity_cap": ("Capitalisation actions", "Equity market cap"),
    "bond_cap": ("Capitalisation obligations", "Bond market cap"),
    "value_traded": ("Valeur échangée (actions)", "Value traded (equities)"),
    "breadth": ("Hausses / baisses / inchangés", "Up / down / unchanged"),
    "composite_history": ("BRVM Composite", "BRVM Composite"),
    "top_gainers": ("Plus fortes hausses", "Top gainers"),
    "top_losers": ("Plus fortes baisses", "Top losers"),
    "none_rose": ("Aucune valeur en hausse sur cette séance.", "No stock rose in this session."),
    "none_fell": ("Aucune valeur en baisse sur cette séance.", "No stock fell in this session."),
    "most_traded": ("Valeurs les plus échangées (valeur, FCFA)", "Most traded stocks (value, FCFA)"),
    "sector_ytd": ("Indices sectoriels — variation depuis le 1er janvier", "Sector indices — change since 1 January"),
    "market_cap_history": ("Capitalisation boursière (FCFA)", "Market capitalisation (FCFA)"),
    "equities": ("Actions", "Equities"), "bonds": ("Obligations", "Bonds"),
    "monthly_value": ("Valeur échangée par mois — actions (FCFA)", "Equity value traded per month (FCFA)"),
    "avg12": ("Moyenne 12 mois", "12-month average"),
    # columns
    "symbol": ("Symbole", "Symbol"), "name": ("Société", "Company"), "price": ("Cours", "Price"),
    "change": ("Var. jour %", "Day change %"), "ytd_pct": ("Var. annuelle %", "YTD %"),
    "volume": ("Volume", "Volume"), "value": ("Valeur (FCFA)", "Value (FCFA)"),
    "per": ("PER", "P/E"), "yield": ("Rendement net %", "Net yield %"), "sector": ("Secteur", "Sector"),
    "compartment": ("Compartiment", "Compartment"), "country": ("Pays", "Country"),
    "avg_value_3m": ("Valeur moy./séance 3 mois", "Avg value/session 3M"),
    "last_div": ("Dernier dividende net", "Last net dividend"),
    "div_date": ("Date de paiement", "Payment date"),
    # stock
    "choose_stock": ("Valeur", "Stock"),
    "last_price": ("Dernier cours (ajusté)", "Last price (adjusted)"),
    "return_1y": ("Performance 1 an", "1-year return"),
    "adj_price": ("Cours de référence ajusté (FCFA)", "Adjusted reference price (FCFA)"),
    "volume_adj": ("Volume (titres, ajusté)", "Volume (shares, adjusted)"),
    "dividends": ("Dividendes nets par action (ajustés)", "Net dividends per share (adjusted)"),
    "splits": ("Fractionnements", "Splits"),
    "no_splits": ("Aucun fractionnement depuis 2016.", "No split since 2016."),
    "order_book": ("Carnet d'ordres à la clôture", "Order book at the close"),
    "bid": ("Meilleure offre d'achat", "Best bid"), "ask": ("Meilleure offre de vente", "Best ask"),
    "bid_qty": ("Qté achat", "Bid qty"), "ask_qty": ("Qté vente", "Ask qty"),
    "spread": ("Écart", "Spread"),
    "notices": ("Communiqués et avis", "Notices and releases"),
    "meetings": ("Assemblées générales", "Shareholder meetings"),
    "ratio": ("Parité", "Ratio"), "source": ("Source", "Source"), "evidence": ("Justificatif", "Evidence"),
    "date": ("Date", "Date"), "kind": ("Type", "Type"), "reference": ("Référence", "Reference"),
    "nature": ("Nature", "Nature"), "subject": ("Objet", "Subject"), "time": ("Heure", "Time"),
    "place": ("Lieu", "Venue"),
    "kind_operation": ("Opération en cours", "Ongoing operation"), "kind_avis": ("Avis BRVM", "BRVM notice"),
    "kind_communique": ("Communiqué", "Company release"),
    # compare
    "compare": ("Comparer des valeurs", "Compare stocks"),
    "choose_stocks": ("Valeurs (8 max.)", "Stocks (max. 8)"),
    "rebased": ("Performance (base 100)", "Performance (rebased to 100)"),
    "total_return": ("Performance %", "Return %"), "volatility": ("Volatilité annualisée %", "Annualised volatility %"),
    "max_dd": ("Baisse max. %", "Max drawdown %"),
    "correlation": ("Corrélation des rendements quotidiens", "Correlation of daily returns"),
    "screener": ("Filtre de valeurs", "Stock screener"),
    "per_range": ("PER", "P/E range"), "min_yield": ("Rendement min. %", "Min. yield %"),
    "min_value": ("Valeur moy./séance min. (FCFA)", "Min. avg value/session (FCFA)"),
    "all": ("Tous", "All"), "results": ("{n} valeurs", "{n} stocks"),
    # bonds
    "issuer": ("Émetteur", "Issuer"), "category": ("Catégorie", "Category"),
    "maturity": ("Échéance", "Maturity"), "coupon_rate": ("Taux %", "Coupon %"),
    "nominal": ("Nominal", "Nominal"), "accrued": ("Coupon couru", "Accrued coupon"),
    "next_coupon": ("Prochain coupon", "Next coupon"), "amort": ("Amortissement", "Amortisation"),
    "coupon_vs_maturity": ("Taux de coupon selon l'échéance", "Coupon rate by maturity"),
    "choose_bond": ("Obligation", "Bond"), "bond_price": ("Cours de référence", "Reference price"),
    "traded_by_year": ("Valeur échangée par an (FCFA)", "Value traded per year (FCFA)"),
    "bonds_listed": ("{n} obligations cotées", "{n} listed bonds"),
    # funds
    "manager": ("Société de gestion", "Manager"), "nav": ("Valeur liquidative", "NAV"),
    "nav_date": ("Date VL", "NAV date"), "perf_1y": ("Perf. 1 an %", "1Y return %"),
    "perf_3y": ("Perf. 3 ans %", "3Y return %"), "choose_funds": ("Fonds (4 max.)", "Funds (max. 4)"),
    "nav_chart": ("Valeur liquidative (base 100)", "NAV (rebased to 100)"),
    "funds_count": ("{n} fonds", "{n} funds"),
}

SECTOR_CODES = {  # 2025+ classification (sector_code in equity_quotes)
    "TEL": ("Télécommunications", "Telecommunications"), "FIN": ("Services financiers", "Financials"),
    "CB": ("Consommation de base", "Consumer staples"), "CD": ("Consommation discrétionnaire", "Consumer discretionary"),
    "ENE": ("Énergie", "Energy"), "IND": ("Industriels", "Industrials"), "SPU": ("Services publics", "Utilities"),
    "AGR": ("Agriculture", "Agriculture"), "DIS": ("Distribution", "Distribution"), "TRP": ("Transport", "Transport"),
    "AUT": ("Autres secteurs", "Other sectors"),
}
FUND_CATEGORIES = {
    "A": ("Actions", "Equity"), "D": ("Diversifié", "Diversified"),
    "OMLT": ("Obligataire moyen/long terme", "Medium/long-term bond"), "OCT": ("Obligataire court terme", "Short-term bond"),
    "OATC": ("Obligataire court terme (OATC)", "Short-term bond (OATC)"), "M": ("Monétaire", "Money market"),
    "C": ("Contractuel", "Contractual"),
}
COUNTRIES = {"CI": ("Côte d'Ivoire", "Côte d'Ivoire"), "SN": ("Sénégal", "Senegal"), "BF": ("Burkina Faso", "Burkina Faso"),
             "BJ": ("Bénin", "Benin"), "ML": ("Mali", "Mali"), "NE": ("Niger", "Niger"), "TG": ("Togo", "Togo"),
             "GW": ("Guinée-Bissau", "Guinea-Bissau")}


def lang() -> str:
    return st.session_state.get("lang", "fr")


def t(key: str, **kw) -> str:
    fr, en = LABELS.get(key, (key, key))
    s = fr if lang() == "fr" else en
    return s.format(**kw) if kw else s


def name_of(mapping: dict, code) -> str:
    if code is None or (isinstance(code, float) and math.isnan(code)):
        return ""
    pair = mapping.get(code)
    return (pair[0] if lang() == "fr" else pair[1]) if pair else str(code)


def _sep(s: str) -> str:
    """Python '1,234.56' -> French '1 234,56' (narrow no-break space as thousands separator)."""
    return s.replace(",", " ").replace(".", ",") if lang() == "fr" else s


def fmt_num(x, decimals: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return _sep(f"{x:,.{decimals}f}")


def fmt_pct(x, decimals: int = 2, signed: bool = True) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return _sep(f"{x:+,.{decimals}f}" if signed else f"{x:,.{decimals}f}") + " %"


def fmt_amount(x) -> str:
    """Large FCFA amounts: FR '13 277 Mds' / '1 467 M', EN '13.28 tn' / '1.47 bn'."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if lang() == "fr":
        if abs(x) >= 1e9:
            return fmt_num(x / 1e9, 0 if abs(x) >= 1e11 else 1) + " Mds"
        return fmt_num(x / 1e6, 0) + " M"
    if abs(x) >= 1e12:
        return f"{x / 1e12:,.2f} tn"
    if abs(x) >= 1e9:
        return f"{x / 1e9:,.2f} bn"
    return f"{x / 1e6:,.0f} m"


_MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


_MONTHS_FR_FULL = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                   "novembre", "décembre"]
_MONTHS_EN_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                   "November", "December"]
_DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def month_name(m: int) -> str:
    return (_MONTHS_FR_FULL if lang() == "fr" else _MONTHS_EN_FULL)[m - 1]


def weekday_name(d) -> str:
    return (_DAYS_FR if lang() == "fr" else _DAYS_EN)[d.weekday()]


def fmt_date(d) -> str:
    if d is None or d != d:
        return "—"
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    if lang() == "fr":
        return f"{d.day} {_MONTHS_FR[d.month - 1]} {d.year}"
    return d.strftime("%d %b %Y").lstrip("0")


def plotly_separators() -> str:
    """Plotly 'separators' layout value: decimal then thousands character."""
    return ", " if lang() == "fr" else ".,"
