# Request for proposal: how many extra rooms should we sell?

**From:** Director of Revenue, a two-hotel group in Portugal
**To:** RateGain Revenue Science team
**Document owner:** Kunal Pidiha, Client Lead. **Challenger:** Nitya. Review and sign-off are pending.

### 1. What is the background?

We run a city hotel in Lisbon and a resort in the Algarve, where cancellations can leave rooms empty. Our current rule uses each hotel's average cancellation rate, multiplied by the night's bookings, minus a fixed number of rooms for safety. We want to know whether another rule can reduce our costs without moving too many arriving guests to other hotels.

### 2. What must the solution do?

1. Give the revenue manager one recommendation for each of the next 14 arrival nights at both hotels: 28 rows, with a whole, non-negative number of extra rooms to sell.
2. Show the hotel, arrival date, booking count, expected cancellations, safety buffer and recommended extra rooms, with a short explanation of the recommendation.
3. Run from a bookings file and a saved method, without retraining, using `python src/nightly.py --from 2017-08-18 --nights 14` for the final demonstration.
4. Compare our flat rule, a lookup table and at least two learned models on the same hotel-nights, using the supplied scoring rule.
5. Deliver the code, saved method, full comparison and tuning tables, run instructions, and limitations so another team member can reproduce the results.

### 3. How good must it be, and on which period?

We will accept a replacement rule only if it costs less than our flat rule on **1 January–31 August 2017**, with **no more than 10 walked guests per 1,000 arrivals** across that period.
Arrivals means scored bookings that did not cancel. The ceiling applies to the whole period and does not guarantee that every night avoids walks. Report both hotels together, show results by hotel as well, and compare exactly the same bookings without dropping difficult nights to improve the result.

Use the `src/contract.py` to calculate costs: cancellation-related empty rooms × the night's average booked stay value, plus walked guests × **€300**.
Booked stay value is nightly rate × stay length.
Report total cost, empty rooms, walked guests, walks per 1,000 arrivals, whether the ceiling was met, and euro savings against the flat rule; show monthly results alongside the period totals.

| Arrival period           | Permitted use                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------ |
| Before 1 July 2016       | Fit methods and calculate each hotel's cancellation rate for the flat rule.          |
| 1 July–31 December 2016  | Compare methods and choose model settings and safety buffers under the walk ceiling. |
| 1 January–31 August 2017 | Evaluate the frozen choice once and report the result.                               |

Choose the flat rule's fixed safety-room allowance on the same choose period. If the proposed rule fails either acceptance condition, report that result and do not recommend it as a proven improvement. We have not set a minimum percentage saving beyond a positive euro saving.

### 4. Within which limits and rules?

Use only inputs known and fixed when the reservation was made, supported by the column audit in `docs/COLUMNS.md`. Keep outcomes separate from prediction inputs, use date-based splits, and do not change settings after seeing the proof results without disclosing the change and both runs. The project's cancellation target includes no-shows.

For this build, use the historical bookings and scoring contract. The data does not supply room inventory by hotel and date, and the contract assumes each night's final bookings are already known; explain both limits before presenting the output as a live selling limit. Pricing changes, automatic selling or relocation, and live booking-system integration are outside this delivery; our revenue manager makes the final decision.

### 5. What data do we provide?

We provide **119,390 bookings and 32 original columns**, covering arrivals from **1 July 2015 to 31 August 2017**, available through `python src/data.py`. The raw data contains **44,224 cancellations (37.04%)**, correcting the brief's estimate of about one in four; this overall rate describes the data and must not replace training-period rates in the flat rule.

The source is Antonio, de Almeida and Nunes (2019), _Hotel booking demand datasets_, CC BY 4.0; source details are in `data/README.md`.

### 6. How will we judge proposals?

First, check the cost and walk-rate conditions above; a cheaper rule that breaks the ceiling is rejected. Among acceptable proposals, prefer one our manager can understand and our team can reproduce and maintain; report measured run time and dependencies, rather than relying on accuracy or a presentation claim alone.

### 7. What is the timeline?

Within the course build week: agree the brief and data checks on Tuesday, compare methods and define the build on Wednesday, and complete the repeatable nightly command on Thursday. Freeze choices before the final proof run, finish reviewed evidence and recordings by Friday, and demonstrate the saved method on Saturday; this is a historical demonstration, with any live pilot agreed separately.

### 8. What may the vendor ask us?

How many rooms are actually available at each hotel on each date, after maintenance closures and group blocks? Do we keep or refund payment when a non-refundable booking cancels or becomes a no-show? Can we provide booking-change timestamps, explain why staff abandoned the previous cancellation list, and share the evidence behind the vendor's claimed 95% accuracy?

### 9. What is on the wish list?

Our marketing team would love to find our hidden guest types.
