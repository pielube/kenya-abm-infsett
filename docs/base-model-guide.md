# Kenya informal settlements base model guide

The model explores how households obtain and change electricity access when formal and informal supply differ in price, reliability, perceived safety, and trust. Household decisions change the connections attached to electricity poles, which then affect service problems and subsequent decisions. This creates feedback between access, infrastructure, affordability, and attitudes.

This purpose is inferred from the implemented rules. The model's Info tab contains an unfilled template, including its credits and references. The supplied files do not establish an empirical calibration, a particular settlement map, or a validated prediction for Kenya. The model is best read as an experimental representation of these mechanisms until that supporting evidence is supplied.

The reference implementation is [kenya_informal_settlements.nlogox](../models/kenya_informal_settlements.nlogox), saved in NetLogo 7.0.3. The explicit base configuration is [base.json](../experiments/base.json). The description below follows active code where comments disagree with it.

## Aim and questions the model can explore

The implemented mechanisms support questions such as:

- How do price and attitudes jointly influence formal versus informal electricity access?
- How do outages, unmet demand, and safety experiences change attitudes and connection choices?
- How does enforcement affect informal connections, disconnection, and attitudes toward the formal provider?
- How do network reach, pole capacity, and household income influence access and its distribution?
- Can negotiation and satisfactory service sustain relationships with informal providers?

The two providers are represented through household costs, rules, and attitudes. The code calls the formal provider KPLC and informal power distributors IPDs. Neither provider is a separate decision-making agent with its own finances, staffing, or strategy.

## Entities and space

| Component | Representation and role |
| --- | --- |
| Households | Stationary `houses` agents with heterogeneous income, demand, informal fees, budgets, payment histories, and attitudes. |
| Electricity poles | Stationary `poles` agents with capacity, recorded usage, overload status, and connection counts. |
| Formal connections | Directed links from a pole to a household. The household pays metered electricity charges and any outstanding connection installments. |
| Informal service drops | Directed links from a pole directly to a household. The household pays a flat monthly fee. |
| Informal hook-ons | Directed links from a formally connected household to another household. The recipient pays a flat monthly fee and depends on its host's connection. |
| Pole connections | Directed links from a new pole to the nearest existing pole. They display network structure; the code does not calculate electrical flows or shared upstream constraints through them. |
| Patches | The spatial grid used to locate poles and measure reach. It contains no household land use or geographic data layers. |

The world contains 65 by 65 patches, from -32 to 32 on both axes, with no wrapping. Household coordinates are random continuous positions in this abstract world. Connection limits and incident radii are distances in model space; the files provide no conversion to metres.

Household `connection-status` has three values: `"f"` for formal, `"i"` for informal, and `"n"` for unconnected. Service drops and hook-ons are separate link types within the informal category. These describe connection arrangements: an overloaded household remains formally or informally connected even when it receives no electricity that week.

During a run, formal households are blue, informal service drop recipients red, and hook-on recipients light pink. Disconnected households are generally gray. Poles are green when available and magenta when overloaded. Immediately after setup, household colors have not yet been updated to this scheme, so connection state is the reliable starting classification.

## Initial conditions

`setup` clears the world, creates the households, assigns their characteristics, builds the poles and initial formal connections, and resets the tick counter.

Each household receives:

- Monthly income equal to `min-income + random-gamma 2 0.0002`. With NetLogo's shape and rate convention, the base distribution has theoretical mean income 10,500 currency units per month, including the floor of 500. This follows the expression and the installed NetLogo dictionary; the old comment suggesting mean income near 400 does not describe the active code.
- A demand coefficient drawn from a normal distribution with mean 0.003 and standard deviation 0.0003. Monthly demand is `min-demand + income * demand-per-unit-income`. The base theoretical mean is approximately 33.5 kWh per month. These are distribution expectations, not measured sample means.
- An informal flat fee drawn uniformly from 200 up to 500 per month. It is drawn independently of income, despite comments suggesting an income-based fee.
- Independent Boolean attitudes toward KPLC and IPDs. The base probabilities of initially positive attitudes are 40% and 60%, respectively; realized percentages vary with the random draw.
- A desired monthly electricity spending amount, calculated as `income * ln(max-income + 100 - income) / 180`. This sets a lower desired spending share for higher-income households. It is an aspiration used to judge spending pressure; it does not reserve the remainder of income for other expenses.
- A formal tariff of 23 per kWh if monthly demand is at most 30 kWh, otherwise 28 per kWh. Income, demand, and tariff stay fixed after setup.

The code's comments identify currency as Kenyan shillings. These amounts should be understood as model assumptions, rather than claims about current Kenyan prices or income distributions.

The first pole is placed at a randomly selected patch satisfying `count houses-here != 1`. This unusual condition permits empty patches and patches with multiple households; it does not specifically select an occupied patch. Further poles are added within `pole-connection-limit` of existing poles. Candidate sites are ranked by the sum of income of households within formal reach that currently have no pole in range. Network growth therefore prioritizes reachable unserved income, rather than simply household counts.

At each new pole, initially formal connections are offered to households above the income percentile defined by `initial-formal-pct`, provided they are within formal reach and still unconnected. With the base value 50, the richest half are eligible. Geographic reach means this does not guarantee that exactly 50% start formally connected. Everyone else starts unconnected; there are no initial informal links.

A setup-only check with the base inputs and seed 42 produced 995 formal households (49.75%), 1,005 unconnected households (50.25%), and no informal households. The realized positive attitude shares were 40.45% for KPLC and 59.35% for IPDs. Mean income was 10,691.90 and mean monthly demand was 34.109 kWh.

During network construction, existing formal customers repeatedly receive randomized remaining installment counts from 0 to 23 and missed installment counts from 0 to 5. Thus initial formal customers represent relationships with different payment histories. Households that start unconnected retain the initial 24 remaining installments.

The poles are all built during setup. The active base run does not add households, extend the pole network, change incomes, or increase capacity over time.

## Time and execution order

One `go` call represents approximately one week. Financial routines run every four ticks, using a simplified four-week month. The default base run lasts 52 ticks, equivalent to 13 of these model months. The active stopping rule is 1,480 ticks, equivalent to 370 model months. Comments referring to 480 ticks are stale.

Within each tick, the order is:

1. Clear household issue and switching flags.
2. At a month boundary, reset household cash to income, reset monthly expense, and potentially worsen attitudes when the spending-pressure index exceeds its threshold.
3. Call `policy-intervention`, whose scenario blocks are all commented out.
4. Determine blackouts from the recorded pole usage.
5. At a month boundary, allow eligible informal customers to negotiate a lower fee.
6. At a month boundary, bill connection installments and informal flat fees.
7. Account for weekly electricity use, formal usage payments, unmet demand, outages, spending ratios, and the spending-pressure index.
8. Generate safety incidents and their local attitude effects.
9. Allow satisfactory service to improve attitudes toward the current provider.
10. Disconnect some nonpaying customers and allow unconnected households to attempt informal access.
11. Allow households with an issue to consider changing provider.
12. Update pole connection counts and carry out enforcement when due.
13. Update the duration of informal relationships and display colors, then advance the tick.

Month boundaries include tick 0. Enforcement also includes tick 0. Consequently, the first `go` call includes billing and an enforcement sweep; the initial `setup` state is distinct from the state after the first week.

Agent actions within `ask` blocks use NetLogo's randomized agent order. Several routines modify connections that later actions depend on, so the model is stochastic in both its inputs and its sequence of local interactions. The runner supplies seed 42 for the base case; the seed command inside `setup` is commented out.

## Household costs and spending pressure

Formal weekly electricity charges equal `demand * tariff / 4`. During an outage, formal usage and metered electricity payment are skipped. Connection installments can still be charged at the month boundary. A household short of cash buys only what its remaining cash allows, records an issue, and may lose its positive KPLC attitude.

`formal-connect-fee = 625` is the amount charged for each outstanding monthly installment. The code does not divide 625 by 24. A household with all 24 installments outstanding would pay 15,000 in installments if it completes them. Existing customers may owe fewer installments, and returning formal customers retain credit for previously completed installments.

Informal customers pay a flat monthly fee, irrespective of their actual consumption and outage experience. Once connected, consumption is not conditional on having paid that month's fee; nonpayment instead exposes the household to later disconnection. Customers with `spend-ratio > 1` can negotiate at month boundaries. This eligibility test uses the preceding tick's ratio, generally the previous month's closing ratio, because the ratio is recalculated later in the tick. The probability is their continuous informal relationship length divided by four, interpreted as a percentage. A successful negotiation lowers the fee by 10, down to the minimum of 200.

For illustration, a household with income 10,000 and demand coefficient 0.003 has monthly demand 32 kWh under the base minimum demand. Its formal usage cost is 896 per month, plus 625 while installments remain. An informal fee of 350 would be substantially cheaper. This is an arithmetic example of the rules, not a measured representative household.

`HH-budget` is available cash and resets to total monthly income. It does not accumulate savings between months, and the model does not deduct food, rent, or other household costs.

`spend-ratio` is cumulative electricity spending in the current model month divided by the desired monthly electricity expense. Whenever it exceeds one, the code adds `spend-ratio - 1` to `debt`. This can happen in several weeks of the same month. Accordingly, `debt` is a dimensionless index of accumulated spending pressure. It is separate from the missed-payment counters, does not represent unpaid shillings, and resets when the household obtains a new formal or informal connection through the switching helpers.

## Reliability and safety

A pole is marked overloaded when its recorded `pole-usage` exceeds its capacity. Its formal customers, service drops, and hook-on recipients then experience an outage. The base blackout setting is `only-hurt-kplc`: affected households can lose positive KPLC attitudes, including households using informal supply. IPDs can therefore remain attractive while relying on the same infrastructure.

The load accounting has a material implementation issue: weekly consumption is added to the existing pole usage, without a regular weekly reset. Usage is reset to zero when overloaded households are processed. The blackout check precedes that week's consumption. Thus the implemented mechanism compares capacity against accumulated usage from preceding weeks, which can produce recurring loading and outage cycles. A plot of `pole-usage / pole-capacity` must retain this meaning until that mechanism is changed.

The informal connection capacity is 13 kWh per week. Direct service drops add at most that amount to pole usage. In the branch where demand exceeds this limit, hook-ons still add their full demand to the supplying pole, while recording unmet demand as an issue. The two connection types therefore do not apply the cap consistently.

Safety incidents are sampled among informal households whose connections are not overloaded. Incident probability is the number of cached informal neighbors within `r1`, multiplied by `incidents-multiplier`, interpreted as a percentage each week. With multiplier 5, 20 qualifying neighbors make the event certain. Affected households can lose positive IPD attitudes, and households within `r2` can also lose positive IPD attitudes.

Safety incidents change issues and attitudes. They do not remove households, cause modeled injuries or deaths, damage links, or charge financial losses. A neighbor affected by someone else's incident is not automatically given an issue flag; satisfactory service later in the same tick can restore its IPD attitude.

The interface input `incidents-radius` is unused in the active procedures. The actual incident and influence radii are `r1` and `r2`.

## Attitudes and connection decisions

Attitudes are independent Boolean flags, allowing four combinations: like both providers, like KPLC only, like IPDs only, or like neither. Exported fields called `trust_kplc_pct` and `trust_ipd_pct` measure the percentage with a positive flag, rather than mean continuous trust scores.

Blackouts, spending pressure, unmet demand, safety incidents, and enforcement can worsen attitudes, using their corresponding probability parameters. A week with no issue gives a connected household a 50% base chance of a positive attitude toward its current provider. These flags can consequently change frequently.

Only connected households with an issue that tick, and without an earlier recorded switch that tick, consider voluntary provider switching. They compare the alternative's predicted monthly cost with their current arrangement. Formal predicted cost assumes the full monthly demand at the fixed tariff, plus an installment when still owed. Informal predicted cost is the household's flat fee. These comparisons do not explicitly forecast outages or adjust expected cost for unmet demand.

The exact base switching probabilities are:

| Positive toward current provider | Positive toward alternative | Alternative strictly cheaper | Alternative equal or more expensive |
| --- | --- | --- | --- |
| Yes | Yes | 40% | 20% |
| Yes | No | 0% | 20% |
| No | Yes | 50% | 10% |
| No | No | 40% | 10% |

The table follows the order of the active conditional branches in both directions. These are conditional chances of attempting a switch, and successful connection also requires a reachable destination. The four `p-switch-*` inputs are separate conditional probabilities and need not sum to 100.

When obtaining informal access, a household first seeks the nearest eligible pole for a direct service drop. It considers a hook-on to a formally connected neighbor only if no eligible pole is available. Eligible sources must have non-overloaded relevant links. This priority is the reverse of one nearby comment in the code.

When obtaining formal access, the household selects the nearest pole within formal range. This routine does not screen the pole for overload or require an upfront affordability check. Unconnected households have a 25% weekly chance of attempting informal access; there is no direct unconnected-to-formal search rule.

A formal household that switches to informal supply loses its formal link and any hook-ons it was hosting. Its dependent households become unconnected. A host disconnected for unpaid installments also disconnects its hook-on recipients. These dependencies allow one household's connection change to affect several others.

## Nonpayment and enforcement

An informal household with any recorded missed flat-fee payment has a 30% weekly chance of disconnection. A formal household is disconnected once its missed installment count exceeds five. Successful payments do not clear previous misses; these are accumulated misses, rather than necessarily consecutive missed months. The corresponding counter is reset when the household enters a new connection through the relevant switching helper.

The later unconnected-household loop does not check the switched-this-tick flag. As a result, a household disconnected for nonpayment can attempt informal reconnection in the same tick, despite comments describing a general limit of one change per tick.

Every 110 ticks in the base configuration, including tick 0, enforcement targets the five poles with the most informal connections. It removes direct informal drops and hook-ons attached through those poles' formal households. Affected informal households may lose positive KPLC attitudes. Enforcement removes links; it does not fine households, change pole capacity, or remove poles.

The 52-tick base run therefore includes only the initial enforcement sweep. The full 1,480-tick run includes sweeps at 0, 110, and subsequent multiples through 1,430.

`switchcount` combines several event types. It counts initial informal connection acquisition, voluntary provider changes, and some involuntary disconnections. Enforcement removals and hook-on recipients losing service because their host switches are not counted. Its exported mean is a mixed connection-event counter, rather than a complete count of voluntary provider changes.

## Base parameters

All 36 base inputs match the values saved in the model interface. Distance values use model spatial units.

| Inputs | Base values |
| --- | --- |
| `n-households`, `n-poles`, `initial-formal-pct` | 2,000 households; 100 poles; richest 50% eligible for initial formal access |
| `min-income`, `min-demand` | 500 monthly income floor; 2 kWh monthly demand floor |
| `min-informal-fee`, `max-informal-fee` | 200 and 500 monthly fee bounds |
| `formal-connect-fee` | 625 per outstanding monthly installment |
| `pole-max-capacity`, `informal-connection-capacity` | 180 pole capacity; 13 kWh per week informal capacity, with accounting qualifications above |
| `pole-connection-limit`, `formal-connection-limit` | 5 and 5 |
| `informal-sd-limit`, `hookon-limit` | 4 and 3 |
| `enforcement-number`, `enforcement-freq` | 5 poles every 110 ticks, including tick 0 |
| `init-attitude-kplc`, `init-attitude-ipd` | 40% and 60% probability of positive initial attitude |
| `debt-threshold` | 10 spending-pressure index units |
| `p-switch-cost-only` | 40% |
| `p-switch-attitude` | 10% |
| `p-switch-all-factors` | 50% |
| `p-switch-cost-despite-attitude` | 20% |
| `a-switch-blackout`, `a-switch-debt`, `a-switch-safety`, `a-switch-demand`, `a-switch-enforcements`, `a-switch-satisfaction`, `a-switch-safety-other` | Each 50% |
| `blackouts-attitude`, `blackout-mitigation-pct` | `only-hurt-kplc`; 50%, which is inactive in this selected blackout branch |
| `incidents-multiplier`, `incidents-radius`, `r1`, `r2` | 5; unused input 1; actual incident radius 2; attitude influence radius 2 |
| Run settings | Seed 42; default horizon 52 ticks; active model stopping point 1,480 ticks |

The `bau` helper is marked as needing an update. It uses an enforcement interval of 48 and a cost-only switching probability of 20, and omits several current controls. It is a different configuration from the explicit base profile used by the runner.

## Existing base results

The source model and archived model copies in `results/base/runs/52_ticks/` and `results/base/runs/1480_ticks/` share SHA256 `859d920dcb381ebdffc381525c24747d0dff3d7fbd315959f540cd9dd957c987`, matching [source.json](../models/source.json). Both executions use seed 42 and identical parameter values, with horizons of 52 and 1,480 ticks. Their saved runner versions differ. The [base results archive](../results/base/README.md) also preserves the later diagnostic observations and publication figures.

| Recorded result | At tick 52 | At tick 1,480 |
| --- | --- | --- |
| Formal households | 578 / 28.9% | 1,067 / 53.35% |
| Informal households | 1,254 / 62.7% | 835 / 41.75% |
| Unconnected households | 168 / 8.4% | 98 / 4.9% |
| Informal service drop recipients | 1,115 / 55.75% | 608 / 30.4% |
| Hook-on recipients | 139 / 6.95% | 227 / 11.35% |
| Positive KPLC attitude | 8.6% | 32.4% |
| Positive IPD attitude | 39.1% | 40.6% |
| Mean spending-pressure index `debt` | 2.5718 | 2.1769 |
| Mean mixed event counter `switchcount` | 6.886 | 130.391 |
| Overloaded poles | 35 of 100 | 29 of 100 |

These are recorded endpoints from [the short run](../results/base/runs/52_ticks/results.csv) and [the full run](../results/base/runs/1480_ticks/results.csv), each using one seed. They establish the composition at those endpoints, not an ensemble average, an equilibrium, or the path taken between them. For example, declining outstanding installments are a plausible mechanism to investigate when explaining later formal access; these two rows alone cannot establish that explanation.

The ordinary runner sets `runMetricsEveryStep="false"`, so these two endpoint CSVs contain final results only. The later [diagnostic collection](../results/base/data/) adds weekly aggregates, pole records, observed status transitions, selected household cross-sections, and link-network snapshots. Its results match both original endpoints. See the [figure guide](base-figures.md) for the resulting views and their interpretation.

## Visualizations for understanding a base run

| View | What it would help explain | Required output |
| --- | --- | --- |
| Access shares over time | Entry into informal supply, changes in formal access, and disconnection episodes | Per-tick formal, service drop, hook-on, and unconnected counts |
| Provider attitudes over time | How experience and connection choices interact | Per-tick positive attitudes and all four attitude combinations, ideally by connection type |
| Pole load and outages | The accumulation and reset mechanism and which households lose service | Per-tick pole usage, capacity, overload status, and affected household counts |
| Spatial network snapshots | Reach, access gaps, clusters, and hook-on dependence | Household and pole coordinates, states, and directed links at selected ticks |
| Household affordability by income | Who pays above their desired amount and who cannot meet demand | Income, demand, desired expense, actual expense, budget, payment history, connection status, and spending pressure |
| Connection transitions and event reasons | Whether churn comes from voluntary decisions, nonpayment, enforcement, or loss of a host | Events recording tick, household, old and new status, and reason |
| Individual household histories | How costs, attitudes, service issues, and connection choices combine | Repeated household observations with the relevant issue and payment flags |

The archived observations now support access and attitude trajectories, outage diagnostics, income comparisons, and selected spatial snapshots. Generic provider switches still cannot be attributed reliably to one issue using the current Boolean `issues-this-tick` alone: multiple problems can occur in the same week, so reason flags or event records would be needed for causal diagnostics. Adjacent recorded statuses also cannot recover changes reversed within a week.

The NetLogo interface already contains plots of access, attitudes, cost advantage, budgets, fees, overspending, and overloads. Its attitude plot divides counts by 20, which gives percentages only when there are exactly 2,000 households. The exported attitude reporters correctly divide by actual population. Some monitors use colors; state and link reporters are more suitable for analysis, especially immediately after setup.

## Other implementation details to retain

- `nearby-houses` is cached while households are being created and positioned. A real-engine setup check confirmed that later position changes leave valid neighbors missing. At base seed 42, 1,829 of 2,000 households have an incomplete cache within hook-on radius 3; mean valid cached neighbor count is 6.443, compared with 12.814 actual neighbors. Within the incident and attitude radius 2, 1,654 households have incomplete caches; mean cached count is 3.0035 versus 5.970 actual neighbors. Hook-on searches and safety effects therefore operate on incomplete spatial neighborhoods. Direct pole searches do not use this cache.
- The blackout chooser includes other scenarios, but their labels do not always fully describe the branch logic. In `hurt-both-providers`, formal customers can lose KPLC attitude and informal customers can lose IPD attitude; an informal household does not directly lose both attitudes in that branch. Mitigation scenarios change issue and attitude handling, without providing explicit replacement electricity.
- All policy-intervention scenarios are commented out. The present base case includes routine enforcement but no later trust campaign, capacity expansion, or scenario change.
- The 19 embedded BehaviorSpace experiments contain legacy variable names and should not be treated as current executable experiment definitions. The Python runner generates experiments from [model.json](../experiments/model.json) instead.

The setup diagnostic used the unchanged model, all base parameters, and seed 42. Its experiment called `setup` followed by an inert `tick`, rather than the model's `go`, so its results file reports tick 1 while its household attributes and connections describe setup before any model dynamics. The [diagnostic provenance](../results/base/setup/provenance.json) records exact reporters, source hash, and execution details; [named diagnostic results](../results/base/setup/diagnostics.json) include the initial state and cache comparisons.

## Code navigation

Line numbers refer to the unchanged source model described above.

| Subject | Procedure and starting line |
| --- | --- |
| Agent types and state | Breed, household, pole, and link declarations, lines 16 to 61 |
| Initialization | `setup`, line 79 |
| Tick schedule | `go`, line 131 |
| Pole growth and initial connections | `build-network`, line 170; `add-a-pole`, line 191; `establish-connections`, line 212 |
| Budget reset and spending pressure response | `earn-income-budget`, line 230 |
| Inactive intervention scenarios | `policy-intervention`, line 248 |
| Overload classification | `blackouts`, line 279 |
| Informal fee negotiation | `negotiate`, line 305 |
| Monthly fixed payments | `monthly-billing`, line 329 |
| Consumption, weekly payment, issues, and spending pressure | `per-week`, line 388 |
| Local safety effects | `safety-incidents`, line 488 |
| Positive attitude recovery | `service-satisfaction`, line 508 |
| Nonpayment disconnection and informal entry | `add-drop-connections`, line 524 |
| Conditional provider switching | `switch-connections`, line 569 |
| Enforcement | `enforcement-actions`, line 617 |
| Connection creation and removal | `switch-to-informal`, line 710; `switch-to-formal`, line 747 |
| Initial income cutoff | `wealthy-potential-connections`, line 770 |
| Cost comparison helpers | Reporters beginning at lines 778, 783, 790, and 798 |
| Interface and saved defaults | Widgets beginning at line 848 |
| Exported metrics | [experiments/model.json](../experiments/model.json) |
| Experiment generation and final-only recording | [run_model.py](../run_model.py), `experiment_xml`, line 174 |
