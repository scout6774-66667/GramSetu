# GramSetu AI — Time-Series Feature & Leakage Prevention Audit
**Document ID:** `P4-05-FEATURE-LEAKAGE-AUDIT`  
**Prediction Target:** Next observed calendar day's modal wholesale price ($P_{\text{modal}}$, INR/quintal) for $(\text{market} \times \text{commodity} \times \text{variety} \times \text{grade})$.  
**Feature Order:** `["lag_1", "lag_7", "lag_14", "lag_28", "rolling_mean_7", "rolling_std_7", "dow_sin", "dow_cos", "doy_sin", "doy_cos"]`  

---

## 1. Mathematical Feature Contracts

### Exact Calendar Lags (No Lookahead)
GramSetu AI strictly avoids "previous row" approximations. If an auction was closed or data was unrecorded on an exact lag date, the lag is identified as missing:

1. $\text{lag\_1} = P(T - 1\text{ day})$: Prior calendar day modal price.
2. $\text{lag\_7} = P(T - 7\text{ days})$: Same day-of-week prior week price.
3. $\text{lag\_14} = P(T - 14\text{ days})$: Two-week cyclical baseline.
4. $\text{lag\_28} = P(T - 28\text{ days})$: Monthly cyclical baseline.
5. $\text{rolling\_mean\_7} = \frac{1}{7} \sum_{i=1}^7 P(T - i\text{ days})$: 7-day trailing average.
6. $\text{rolling\_std\_7} = \sqrt{\frac{1}{7} \sum_{i=1}^7 (P(T - i\text{ days}) - \text{rolling\_mean\_7})^2}$: 7-day price volatility.
7. Trigonometric Calendar Features:
   $$\text{dow\_sin} = \sin\left(\frac{2\pi \cdot \text{dow}}{7}\right), \quad \text{dow\_cos} = \cos\left(\frac{2\pi \cdot \text{dow}}{7}\right)$$
   $$\text{doy\_sin} = \sin\left(\frac{2\pi \cdot \text{doy}}{365.25}\right), \quad \text{doy\_cos} = \cos\left(\frac{2\pi \cdot \text{doy}}{365.25}\right)$$

---

## 2. Leakage Prevention Protocol

1. **Strict Temporal Causality**:
   - Only observations with $\text{observed\_date} < T_{\text{target}}$ are accessible during feature calculation.
   - Any record where $\text{observed\_date} \ge T_{\text{target}}$ raises `DataGateError("Inference history includes future/target data")`.
2. **Zero Ground-Truth Interpolation**:
   - Missing daily prices are NEVER interpolated linearly or projected forward into ground-truth evaluation sets.
   - If an exact lag is missing, the sample is excluded from model evaluation, with explicit counters recorded in the training report.
3. **Chronological Splitting**:
   - Random $K$-fold cross-validation is strictly prohibited.
   - Splits must be chronological:
     - **Training Split**: Earliest dates up to $T_{\text{split}} - 270\text{ days}$.
     - **Validation Split**: Intermediate 90 calendar days (used solely for algorithm and hyperparameter selection).
     - **Held-Out Test Split**: Final 180 calendar days (evaluated once for final generalization check).

---

## 3. Leakage & Split Integrity Verification

- **Cross-Split Boundary Audit**: Verified that zero target-date modal prices in the validation or held-out test splits appear in the training feature matrix.
- **Preprocessing Scope**: Feature normalization (scaling / centering) is computed strictly on the training partition and applied out-of-sample to validation and test.
