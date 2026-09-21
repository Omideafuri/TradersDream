# PHASE 9B SEALED HOLDOUT MANIFEST
**Sealed Timestamp**: 2026-09-21T22:41:26.236087+00:00  
**Status**: **`SEALED & IMMUTABLE`**  
**Policy**: Chronological non-overlapping splits (60% Dev / 20% Val / 20% Holdout). Shuffling strictly prohibited.

---

## Sealed Asset Partitions

| Asset | Total Rows | Dev Rows (60%) | Val Rows (20%) | Holdout Rows (20%) | Holdout Start UTC | Holdout End UTC | Holdout SHA256 |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- |
| **BTC** (BTCUSDT) | 26,000 | 15,600 | 5,200 | 5,200 | `2026-09-03T21:20:00+00:00` | `2026-09-21T22:35:00+00:00` | `46fc45fa9bdef5da...` |
| **ETH** (ETHUSDT) | 26,000 | 15,600 | 5,200 | 5,200 | `2026-09-03T21:20:00+00:00` | `2026-09-21T22:35:00+00:00` | `ae380cc74aa73d15...` |
| **SOL** (SOLUSDT) | 26,000 | 15,600 | 5,200 | 5,200 | `2026-09-03T21:25:00+00:00` | `2026-09-21T22:40:00+00:00` | `2e7fba2c041d9856...` |

---

## Detailed Partition Hashes

### BTC (BTCUSDT)
- **Full Dataset SHA256**: `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515`
- **Development (60%)**: `2026-06-23T07:00:00+00:00` to `2026-08-16T10:55:00+00:00` (15,600 bars) | Hash: `253557a028e626ba05848658220b4f9057f03ff8f9608445c9fe71e75a8b62e7`
- **Validation (20%)**: `2026-08-16T11:00:00+00:00` to `2026-09-03T21:15:00+00:00` (5,200 bars) | Hash: `f24d8f97961bfc0977a49928c3a371071b9e4e79ff154b9e9e602a96cd8a2714`
- **Sealed Holdout (20%)**: `2026-09-03T21:20:00+00:00` to `2026-09-21T22:35:00+00:00` (5,200 bars) | Hash: `46fc45fa9bdef5dabcc61b7a433c3791f633941157244fda81e669ab8a5b6148`

### ETH (ETHUSDT)
- **Full Dataset SHA256**: `f5de00e066017bfaefbaa6ada2bd97ff0cb460366651d0076c918c6e6d5e51eb`
- **Development (60%)**: `2026-06-23T07:00:00+00:00` to `2026-08-16T10:55:00+00:00` (15,600 bars) | Hash: `777b902916dadf0dc03fe5fc51291248a9e6f52484974de824f06d7612b0c947`
- **Validation (20%)**: `2026-08-16T11:00:00+00:00` to `2026-09-03T21:15:00+00:00` (5,200 bars) | Hash: `cb6625e7d261caa10387ceecb0ec05e0c0a1a6fe2e9c9e535c130ea8a09cd635`
- **Sealed Holdout (20%)**: `2026-09-03T21:20:00+00:00` to `2026-09-21T22:35:00+00:00` (5,200 bars) | Hash: `ae380cc74aa73d159d88239e6c89e88f4989a6666d89cfa650a38b64295a63cd`

### SOL (SOLUSDT)
- **Full Dataset SHA256**: `7a128e5aafb7f5b81ff8c01c8b7fd906459a2b455be9354714e858f8e6672f9d`
- **Development (60%)**: `2026-06-23T07:05:00+00:00` to `2026-08-16T11:00:00+00:00` (15,600 bars) | Hash: `45a7ebbb766a91c2dd29b9769d1d6e4e46048132b3c9d21edd17e00519ff0747`
- **Validation (20%)**: `2026-08-16T11:05:00+00:00` to `2026-09-03T21:20:00+00:00` (5,200 bars) | Hash: `d481c7edb2a95576166dffc8a09cc68c5c79aede856bcaaf707a77ea490205b8`
- **Sealed Holdout (20%)**: `2026-09-03T21:25:00+00:00` to `2026-09-21T22:40:00+00:00` (5,200 bars) | Hash: `2e7fba2c041d98561c1afd42455bf92012aa4d4d46aff563323b584be719c187`

---

## Holdout Sealing Rules
1. Holdout observations are strictly forbidden from feature extraction tuning, prompt selection, or threshold calibration.
2. Any mutation to the underlying data requires incrementing the dataset version and creating a new holdout seal.
3. The holdout partition is unlocked exclusively during final out-of-sample evaluation.
