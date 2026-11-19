# Attitudes and trust in electricity provider choice

The base model is a useful starting point for studying how provider attitudes and electricity arrangements evolve together. Its current rules do not yet support a strong claim that trust explains consumers' choices beyond income. The most immediate obstacle is an inconsistent switching rule. Other material limitations concern what the attitude flags mean, how they change, which choices they govern, and how economic experiences generate the attitudes being analysed.

This assessment was made on branch `attitude-trust-review`, created from commit `32305f7`, before the selected repairs. All behavioral descriptions and source line references below concern the [archived original NetLogo model](../results/base/runs/52_ticks/model.nlogox), its [original base settings](../experiments/original-base.json), and the archived seed-42 observations. Source SHA256 is `859d920dcb381ebdffc381525c24747d0dff3d7fbd315959f540cd9dd957c987`. The subsequent switching, experience-accounting and decision-log implementation is documented in [model revisions](model-revision.md); the broader research recommendations below remain proposals.

## What the model already contributes

Households have separate attitudes toward KPLC and informal power distributors (IPDs), allowing approval of both, either, or neither. Those attitudes are initially drawn independently of income. Income does not therefore dictate every preference by construction. Experiences can subsequently change attitudes, which influence switching alongside predicted costs and physical access.

The possibility that informal customers blame KPLC for outages on shared infrastructure is particularly useful for a paper about provider perceptions. It makes responsibility attribution an explicit hypothesis rather than assuming consumers always blame their immediate supplier. Safety incidents, enforcement and satisfactory service also provide pathways connecting experience to provider evaluation.

These are substantive strengths for an exploratory mechanism model. They are not empirical evidence that the assumed pathways, probabilities or timescales describe actual households.

## Attitude is the better current label

The variables `attitude-kplc` and `attitude-ipd` are Boolean positive/negative evaluations. A single flag absorbs service satisfaction, spending pressure, unmet demand, safety and enforcement blame. There is no separate neutral or unknown state, strength of conviction, expectation of fair treatment, or willingness to depend on a provider under uncertainty. The output names `trust_kplc_pct` and `trust_ipd_pct` do not change what is represented.

An attitude framing should specify the object being evaluated: the provider, the supply arrangement, or the act of choosing that provider. These differ from an intention to switch and the ability to act. [Ajzen's measurement guidance](https://people.umass.edu/aizen/pdf/tpb.measurement.pdf) distinguishes evaluation, intention and perceived control; the present model does not implement that complete theory.

A trust framing needs a more specific claim about expectations and dependence. [Mayer, Davis and Schoorman](https://www.makinggood.ac.nz/media/1270/mayeretal_1995_organizationaltrust.pdf) distinguish trust from its antecedents and resulting behavior, and discuss perceived ability, benevolence and integrity. Their organizational framework is a conceptual resource, not a validated measurement model for Kenyan electricity customers. For this application, relevant expectations might concern reliable service, honest and predictable charges, fair treatment or help during payment difficulty.

KPLC is represented as an institution, while informal supply is pooled into a category. There are no distinct IPD operators, operator-specific reputations or remembered relationships with a particular seller. Informal fees belong to households rather than suppliers. The current implementation can represent attitudes toward informal supply as a category more readily than interpersonal trust in a local distributor.

Binary states are not inherently unsuitable. A coherent, justified binary abstraction could support a useful paper. Replacing flags with continuous scores alone would not solve the conceptual or causal problems. At minimum, the paper should define exactly what a positive and negative flag mean, and how households without direct experience acquire them.

## The switching rule needs correction before interpretation

The following table is the exact result of the ordered branches in `switch-connections`, lines 572–610. It applies in both directions. A household must have an issue that week and not already have a recorded switch. The probability concerns attempting the relevant switching helper; a reachable destination is still required for success.

| Positive toward current provider | Positive toward alternative | Alternative strictly cheaper | Alternative equal or more expensive |
| --- | --- | --- | --- |
| Yes | Yes | 40% | 20% |
| Yes | No | **0%** | **20%** |
| No | Yes | 50% | 10% |
| No | No | 40% | 10% |

A household that approves of its current provider and disapproves of the alternative becomes more likely to switch when that alternative becomes more expensive. Also, when the alternative is not cheaper, approving of the current provider raises switching probability from 10% to 20%, holding the alternative's attitude fixed. Neither pattern fits a straightforward interpretation of positive attitude as increasing a provider's attractiveness.

For equal or more expensive alternatives, the alternative's attitude has no influence at all. More generally, cost enters as a cheaper/not-cheaper comparison: the monetary size of the difference is unused. The present rule cannot estimate a meaningful willingness to pay for a more trusted provider.

The intended behavioral table should be specified before implementing a fix. Tests should cover all eight combinations, including equality boundaries and unavailable alternatives. Unless an explicit alternative theory is justified, cheaper alternatives should not become less attractive, more favorable alternative attitudes should not reduce their attractiveness, and more favorable current-provider attitudes should not increase the probability of leaving.

## The choice margin is narrower than general provider selection

Initial formal access is assigned to richer households within pole reach, rather than chosen using attitudes. Unconnected households attempt informal access with a fixed 25% weekly probability, independently of both attitudes and predicted costs. They do not directly seek formal access. Formal access is considered later, after obtaining informal access and experiencing an issue.

Consequently, the current attitude mechanism primarily concerns switching by already connected, dissatisfied households. It does not explain initial selection or a symmetric choice after disconnection. An alternative can also be preferred but physically unreachable. Formal and informal searches use different reach and overload restrictions.

This distinction matters empirically. The original [Mathare study by Njoroge and colleagues](https://www.mdpi.com/2073-445X/9/6/206), sections 3.2.1–3.2.2, reports both conditional willingness to obtain affordable formal supply and mistrust of public actors. [de Bercegol and Monstadt's Kibera fieldwork](https://dspace.library.uu.nl/bitstream/handle/1874/430781/1-s2.0-S2214629618303529-main.pdf?isAllowed=y&sequence=1) also documents negotiated access and constraints, including reported threats to some households moving to formal supply. These studies motivate distinguishing preference from feasible action. They do not establish universal behavior among informal providers or calibrate a causal trust effect.

The paper can either explicitly focus on switching among connected households or extend the decision rule to initial and renewed access. It should avoid interpreting observed use as direct evidence of approval or trust.

## Attitude learning is rapid and uneven

Every issue-free week gives a connected household a 50% chance of restoring a positive attitude toward its current provider. Conditional on remaining with that provider, having four such weeks and receiving no intervening negative updates, only 6.25% of initially negative households remain negative. After eight such weeks the proportion is approximately 0.39%. These are conditional analytical consequences, not measured calendar-time recovery rates.

The unused alternative has no comparable routine for positive learning. Unconnected households also have no general positive recovery process. Positive and negative experiences therefore have asymmetric opportunities to change beliefs. This may be defensible, but the timescale and information channels need empirical justification.

Execution order introduces further problems:

- Debt-related negative updates occur before service satisfaction and do not set an issue flag. A household with no subsequent issue can recover a positive attitude in that same tick.
- Neighbors affected by another household's safety incident lose IPD approval without automatically receiving an issue flag. Informally connected neighbors can recover immediately through satisfactory service later that tick.
- Negotiation depends on relationship duration and overspending, but neither checks nor updates attitudes, despite its trust-related comment.
- Switching resets the spending-pressure index but not the month's accumulated expenditure. Costs incurred under an earlier arrangement can therefore contribute to dissatisfaction attributed to the current provider.

The base also starts with higher IPD approval, attributes informal outages to KPLC under its selected scenario, and permits enforcement to reduce KPLC approval. Findings favoring informal providers would need sensitivity analysis of these assumptions. They should not be presented as attitudes emerging without prior directional assumptions.

An explicit event record and update rule would help: record the experience and its attributed provider, then apply a defined memory process. A slower institutional evaluation could be distinguished from immediate satisfaction if the paper genuinely concerns trust. Positive learning about alternatives could be added if interviews or survey evidence support it.

## Income is present through several mechanisms

Income affects electricity demand, tariff category, desired spending, cash availability, initial eligibility and network placement. It therefore influences both provider choices and the experiences that generate attitudes. Informal fees are initially independent of income; there is no explicit income-by-attitude parameter in the switching rule. Income and demand remain fixed throughout the run, so the model does not describe changing earnings, income shocks or household demand adaptation.

However, the base case has a weak fixed-payment affordability margin. Monthly cash resets to total income, without competing household expenses. Under the base bounds, income is at least 500 and informal fees are below 500, so informal customers can afford their fee at monthly billing. In seed 42, the minimum realized income is 628.13, also above the formal installment of 625. The run consequently records no nonpayment disconnections for either provider. Weekly metered consumption can still exhaust available cash.

Most modeled financial dissatisfaction instead concerns spending above a desired electricity allocation. The variable called `debt` accumulates excess spending ratios, not unpaid currency. This distinction must be maintained when arguing that attitudes contribute beyond economic constraints.

The retained observations show a useful economic explanation to investigate for the nonmonotonic income pattern:

| Initial income quintile | Median monthly demand in kWh | Households above nominal informal capacity | Households with lower predicted formal cost at tick 1,480 | Formally connected at tick 1,480 |
| --- | --- | --- | --- | --- |
| Lowest | 11.39 | 0 of 400 | 275 of 400 | 68.25% |
| 2 | 20.29 | 0 of 400 | 36 of 400 | 51.25% |
| 3 | 28.89 | 0 of 400 | 1 of 400 | 43.25% |
| 4 | 41.50 | 16 of 400 | 0 of 400 | 45.25% |
| Highest | 62.91 | 332 of 400 | 0 of 400 | 58.75% |

Nominal informal capacity is 13 kWh per week, or 52 per four-week month; the known inconsistent treatment of hook-ons qualifies this comparison. Predicted prices assume full demand and each household's remaining installments. A lower price does not guarantee equivalent or feasible service.

Lower-income households can acquire a formal price advantage as installments are repaid, while many higher-income households encounter the informal demand cap. Both experiences also affect attitudes. The table is descriptive evidence of these channels, not a decomposition of their causal importance. It comes from [income_summary.csv](../results/attitude_trust_review/income_summary.csv).

## Why controlling for income is insufficient

At tick 1,480, formal connection is associated with positive KPLC attitudes within every income quintile. Among the poorest quintile, 85.09% of KPLC-positive households are formal, compared with 56.90% of KPLC-negative households; the groups contain 161 and 239 households. This pattern is available in [within_income_association.csv](../results/attitude_trust_review/within_income_association.csv).

It does not identify an independent attitude effect. Current-provider experience updates attitudes, attitudes influence switching, and costs, geography, service history and feasible alternatives affect both. Income categories also leave substantial within-group differences. The recorded flags are end-of-tick states, after learning and switching. Households interact and are not independent simulation replications.

There are three different questions to keep separate:

1. **Association:** do households with different attitudes use different providers within income groups? The archived realization exhibits this.
2. **Contribution inside the model:** how much do outcomes change when attitude-related mechanisms are enabled or altered, holding initial economic and spatial conditions fixed? This needs counterfactual runs with coherent rules.
3. **Importance in actual settlements:** do independently measured attitudes improve explanation or prediction beyond costs, income, service and access constraints? This needs empirical measurements and validation.

The second question can support a mechanism-focused paper. It cannot by itself establish the third. Because attitudes already affect decisions by assumption, observing some attitude effect in a simulation is not a substantive validation result.

## A focused route to the proposed paper

Before estimating the importance of attitudes, correct the switching inconsistencies and resolve the known load-accounting and neighborhood-cache problems. Those problems directly generate reliability and safety experiences, so their effects propagate into attitudes. Preserve the original implementation as a reference and assess the effect of each correction separately.

Then define an economical behavioral specification. Keep price magnitude, actual electricity cash constraints, perceived provider attractiveness, switching friction and physical feasibility conceptually separate. A binary attitude model is acceptable if it is justified and its probabilities behave consistently. If graded attitudes are introduced, use them to represent a defined construct and an explicit learning timescale.

Three counterfactual variants would provide a clear starting comparison:

| Variant | Choice mechanism | Question addressed |
| --- | --- | --- |
| Economic and service baseline | Same initial incomes, fees, network, service rules and switching friction; attitude flags do not enter choice probabilities | What behavior arises without attitudinal choice effects? |
| Fixed provider attitudes | Same initial conditions and process rules, plus attitudes that affect choice but do not learn from experience | What do persistent differences in evaluation contribute? |
| Experience-updated attitudes | Same initial conditions and process rules, plus coherent experience-based updating | What does feedback between experience, attitudes and choice contribute? |

Setting all switching probabilities to zero would freeze voluntary switching, not produce a valid cost-based comparison. Similarly, setting all attitudes positive is not equivalent to removing their influence from the present conditional rule.

Allow negotiated fees, pole loading, feasible alternatives and experiences to evolve within each variant. Holding their realized trajectories identical would remove part of the feedback being studied and address a different, controlled-effect question.

Use multiple stochastic replications, matched initial household characteristics and networks, and report differences within income groups. A shared seed alone does not guarantee matched subsequent shocks once behavioral paths change; saved initial worlds or separate process-specific random streams can improve comparisons. Separate the total contribution of attitude mechanisms from the narrower contribution of their learning process. Test alternative blame assumptions and learning persistence, not only initial approval percentages.

Collect decision-time observations: attitudes before choice, costs, actual cash, existing arrangement, available alternatives, issue type, intended destination, attempted switch and realized connection. End-of-week flags and the existing mixed switch counter cannot recover all those margins. Useful outcomes include voluntary switching, provider tenure, disconnection, unmet demand, spending burdens and access by income, alongside aggregate provider shares.

For empirical grounding, elicit provider evaluation separately from specific expectations, intention to switch, and barriers to doing so. If trust is central, distinguish confidence in KPLC as an institution from confidence in a particular reseller. Validate learning and tenure/switching patterns as well as aggregate connection shares. If such data are unavailable, frame the paper as exploring plausible mechanisms under stated assumptions.

## Suggested paper aim

> Explore how provider attitudes, shaped by service experiences and perceptions of responsibility, interact with household affordability and access constraints to shape formal and informal electricity use.

This framing fits the existing model's strengths while leaving the empirical importance of trust open. A more specific trust question could ask when expectations of fair and dependable treatment cause households to retain a provider or accept a price premium, and how income constrains that response. That stronger question would require clearer trust mechanisms and a coherent cost–attitude trade-off.

## Evidence and reproduction

The [descriptive analysis script](../scripts/assess_attitude_data.py) reads existing observations without running or editing NetLogo:

```powershell
python scripts/assess_attitude_data.py
```

It writes compact summaries and [provenance](../results/attitude_trust_review/provenance.json) under `results/attitude_trust_review/`. It is pinned to the original source and profile, and checks equal-size groups, fixed income and demand, and agreement with both original canonical endpoints. The archived base results retain their original interpretation even though the working model has been revised.

Key code locations are initialization at lines 91–114, monthly cash and spending-pressure response at 230–240, negotiation at 305–313, service and expense experiences at 388–482, safety at 488–499, positive recovery at 508–515, unconnected access at 559–562, switching at 572–610, connection feasibility at 710–763, and initial income eligibility at 770–774.
