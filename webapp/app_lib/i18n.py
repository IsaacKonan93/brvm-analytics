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
