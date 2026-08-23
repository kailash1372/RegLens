# RegLens demo script

## 1. The problem (20 seconds)

“Product labels, manufacturer claims, regulatory guidance, and recall records
live in different places. RegLens turns them into one source-grounded Product
Passport without pretending that one threshold can declare a product safe or
unsafe.”

## 2. Catalog and Passport (45 seconds)

Pause on “Did you know?” and show that each impact card exposes an evidence
status, authority, retrieval date, investigation prompt, and official link.
Explain that the feed comes from the backend evidence store rather than
frontend marketing copy.

Then select Alani Nu Cotton Candy. Point out the current U.S.
manufacturer source, extraction timestamp, caffeine, sugar, nutrition,
ingredients, claims, and manufacturer warnings. Emphasize that these are
manufacturer facts from a validated snapshot.

## 3. Deterministic evidence (45 seconds)

Open CELSIUS. Show the computed caffeine comparison and its Health Canada
source. Say: “The U.S. snapshot states 200 mg per serving. The verified Canadian
rule used for comparison states a 180 mg maximum for the applicable category.
That is regulatory context, not a conclusion that this exact U.S. formulation
is sold illegally in Canada.”

## 4. Ask RegLens (60 seconds)

Ask: “Is Celsius okay for children to drink?” Show the separate cards for the
manufacturer fact, Health Canada's under-14 guidance, computed context, and
interpretation. Point out whether the answer is labelled OpenRouter synthesis
or deterministic evidence fallback. Open the cited primary source. Note that
RegLens avoids a medical yes/no answer.

Follow up in the same chat with: “What about Red Bull?” Show that the current
conversation supplies context while product facts and evidence are resolved
again. Conversation history is deliberately session-only and clears on refresh.

Then ask: “Which drinks exceed the verified Canadian caffeine threshold?” The
answer is generated from stored product values and `VERIFIED` rule logic, not
frontend text.

## 5. Compare products (40 seconds)

Compare Fanta Orange Canada with Fanta Orange Saudi Arabia. Point out the market
labels and different 500 ml versus 100 ml serving bases before discussing sugar
or calories; the snapshots and ingredient lists are never merged. Then briefly
compare CELSIUS, C4, and Alani Nu to show the existing energy-drink use case.
All values are loaded from the API, and unavailable structured values remain
visibly pending instead of being inferred.

## 6. Bright Data resilience (45 seconds)

Open Data Health. Explain that fixture mode is used for the development demo.
Show the Brach's collector created and exercised through the CLI, then explain
that other captured IDs remain unwired when their actual outputs fail the
canonical model. With a published valid collector and API token, refresh
triggers Scraper Studio output and validates it before persistence. Demonstrate
a malformed refresh: health degrades while the last valid Passport remains
visible. Repair manually in Scraper Studio, publish, rerun, and show health
returning to Healthy.

## Closing (10 seconds)

“RegLens takes you from a live product label to regulatory evidence—with every
fact, comparison, and interpretation kept in its proper lane.”
