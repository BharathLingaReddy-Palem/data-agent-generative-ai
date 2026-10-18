"""Conservative checks for common unsupported claims in generated commentary.

These checks are not a general factuality proof. Rejected text uses computed facts
instead of being presented as a validated narrative.
"""
import re


def unsupported_claims(text, *, currency_known=False, trend_available=False):
    reasons = []
    if not currency_known and re.search(r'[$€£₹]|\b(?:USD|EUR|GBP|INR|dollars?|rupees?)\b', text, re.I):
        reasons.append('Currency was not supplied in metric metadata.')
    if not trend_available and re.search(r'\b(?:appears? stable|is stable|remains? stable|is growing|is declining|trend is positive|trend is negative)\b', text, re.I):
        reasons.append('No time-series evidence supports a trend claim.')
    if re.search(r'\b(?:proves? that|caused by|root cause is|no (?:linear )?relationship|high[- ]ROI|guaranteed)\b', text, re.I):
        reasons.append('Causality, absence of association or returns were not established.')
    if re.search(r'\b(?:too (?:small|weak) to (?:impact|influence)|well below what would matter|does not meaningfully drive|do not meaningfully drive|would be too small|no meaningful (?:effect|impact|difference))\b', text, re.I):
        reasons.append('Practical importance requires an explicit domain threshold, not only a p-value or effect size.')
    return reasons
