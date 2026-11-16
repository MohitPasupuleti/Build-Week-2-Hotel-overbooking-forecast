# How many extra rooms should each hotel sell?

**Owner:** Kunal Pidiha, Client Lead. **Challenger:** Nitya. Review and sign-off are pending.

### 1. Who is the client, and who pays whom?

In this course brief, a two-hotel group in Portugal pays RateGain for help deciding how many extra rooms to sell: one city hotel in Lisbon and one resort in the Algarve.

### 2. Who decides, and what does a wrong call cost?

The revenue manager decides each morning for the next 14 arrival nights. Too few extra bookings leave rooms empty; too many mean moving guests to another hotel, called a “walk”. The scoring rule charges the night's average booked stay value (nightly rate × stay length) per empty room and €300 per walk.

### 3. What are we deciding, using what information?

Recommend a whole number of extra rooms for each hotel and arrival night. Use information known and fixed at booking, add the booking cancellation probabilities, then subtract a safety buffer. The project's cancellation target includes no-shows.

### 4. Why is the decision made per hotel-night?

Guests arriving at one hotel share its room supply, so they need one combined recommendation. The supplied booking data does not state how many rooms either hotel has available. We can test an extra-booking allowance under the scoring rule, but need room inventory by hotel and date before using it as a live selling limit.

### 5. How will we judge success?

**North star:** euros saved per calendar month. Numerator: flat-rule cost minus our-rule cost on the same hotel-nights. Denominator: one month. Also report total savings for January–August 2017 and cancellation-related empty rooms per month.

**Guardrail:** at most 10 walks per 1,000 arrivals. Numerator: 1,000 × walked guests. Denominator: scored bookings that did not cancel. Check the whole July–December 2016 choose period and, separately, the whole January–August 2017 proof period; monthly checks are additional.

Include both hotels and all records in each period. Cancelled bookings count towards costs, but not the arrivals denominator. With no arrivals, the walk rate cannot be assessed.

```text
Savings against flat rule = flat-rule cost - our-rule cost
Each rule's cost
  +-- Empty rooms x average booked stay value
  +-- Walked guests x EUR 300
Guardrail alongside both costs: walks / arrivals x 1,000 <= 10
```

Reject any rule above the ceiling. Use `src/contract.py` unchanged. It assumes each night's final bookings are already known; live forecasts need a separate check because bookings are still arriving.

### 6. Which brief numbers have we checked?

| Brief claim or requirement | What we found or still need to check |
|---|---|
| About 25% of bookings cancel | 44,224 / 119,390 = **37.04%**, not 25%; 75,166 did not cancel. |
| 119,390 bookings; 32 columns | Both match the raw file, before adding calculated fields. |
| Two hotels | City: 79,330 bookings, 33,102 cancelled (41.73%). Resort: 40,060 bookings, 11,122 cancelled (27.76%). |
| July 2015–August 2017 | Arrival dates run from 1 July 2015 to 31 August 2017. |
| Train before July 2016 | 49,157 bookings, 1 July 2015–30 June 2016. |
| Choose on July–December 2016 | 29,546 bookings, 1 July–31 December 2016. |
| Prove on January–August 2017 | 40,687 bookings, 1 January–31 August 2017. Splits total 119,390 without overlap; no performance claim. |
| €300 per walk; ceiling of 10 per 1,000 arrivals (1%) | Supplied scoring assumptions, not measured from the data. |
| Next 14 nights at both hotels | Required output: 28 recommendations. |
| Vendor claimed 95% accuracy | Unverified; ask for evaluation data, dates and metric definition. |
| Vendor list abandoned within a month | Unverified; ask staff why it was dropped. |

Checked from raw `data/hotels.csv` using `src/data.py` and `src/contract.py`; see `notebooks/01_data_preparation.ipynb`. The flat rule uses training-period rates only. Data: Antonio, de Almeida and Nunes (2019), CC BY 4.0; details in `data/README.md`.

### 7. What is out of scope?

Room pricing, automatic selling or relocation, live integration and other hotels. The PRD will assess whether marketing's request for hidden guest types helps this decision.

### 8. Who owns what?

| Person | Role and main responsibility |
|---|---|
| Kunal Pidiha | Client Lead: charter, RFP, client observations and business limitations. |
| Diksha | Data Lead: data checks, column audit, cleaning decisions and features. |
| Nitya | Model Lead: model comparisons, safety settings and final evaluation. |
| Mohit Pasupuleti | Build Lead: PRD, build plan, nightly command, architecture and roadmap. |

Review pairs follow `docs/ROLES.md`; sign-offs go in `README.md`.

### 9. What is our main question for the client?

When a non-refundable booking cancels or becomes a no-show, does the hotel keep the payment? The data does not tell us. This affects the meaning of lost revenue; meanwhile, we follow the supplied scoring rule.
