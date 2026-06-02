Misc clean-up issues:
- Markers should be inside the polygon instead of centroid
- Use Colors in popup to indicate scores? (hard to read)
- I think there is a mismatch with interactivity and clustering. For now, i should focus on the non-clustering variant.
- Cluster colors are a bit hard to interpret. Not sure what they mean. Should perhaps reflect the "mode" for the suitability?

## First Viable Model

Tracked in tasks 15–18. Key decisions:

- **No clustering** — interaction bugs with controls; revisit later if performance requires it
- **Interactivity on** — interactive controls enabled at national scale
- **Accessibility range slider** (task 15) — two-sided (min/max distance); within range = excellent, degrade symmetrically beyond
- **National scale** — test performance without clustering; file-size budget still applies (task 13)
- **AR5 layer not rendered** — scoring can still use AR5, but no WMS overlay on map (task 18)
- **Greyscale base map only** — no layer switcher for base tiles (task 18)
- **Markers inside polygon** (task 16) — use `representative_point()` instead of centroid
- **Colored scoring in popup** (task 17) — colour-coded badges per dimension for readability


## Fine-tuning the first viable model

### Round 1

- I want interactivity controls for AR5 use as well: one slider for residential buffer, and one for industrial. Everything within the buffer is "terrible". everything beyond 2x buffer is excellent. Gradual step-down in-between.
- Interactivity control for cabin density. (one slider, handle similarly to the above)
- Re-organize popup information: scoring labels first, then additional data like area, "buildings within buffer", etc.


### Round 2

From the recent js optimizations to minimize the html size, it is evident that i probably want more direct control over the html and js side. Moreover, the website is a bit laggy when panning due to the sheer amount of visible markers (i believe, I haven't profiled properly). Making the markers opaque may help, but still...

I therefore want do migrate from folium to direct html/js/css (using leaflet and modern "vanilla" javascript). The core idea is still the same: serve the final result via static website provider. Moreover, the workflow should still be the same, except that the output should probably be a json file (or js file containing a js object definition with the necessary data). Within the html main file for the web site, or the javascript file, there should be a path that points to the relevant data. I am open to other suggestions as well. It is important to keep the end goal in mind, while at the same time keep the developer workflow convenient.

After this has been done, it should be easier (i hope) to experiment and adjust how the app/website works.

Create task 19 with a plan for how to do this, and update readme and github instructions to reflect these planned changes.

### Round 3 - polish

This is starting to look good. I want to do some final polish and bug fixes:
- Bug: Popup labels does not reflect interactively changed values.
- Scoring dimensions should have a short info button that can be hovered or clicked to show what this dimension means
- Styling/layout:
  - Each scoring dimension should have its own "card", with an enable toggle. The current approach has a scoring selection above and settings below. Instead, i want the settings directly next to the toggle.
  - I want a range slider for accessbility instead of two sliders. If this is complicated with vanilla javascript, perhaps there are some lightweight libraries/frameworks that can be utilized?
  - I want to support two languages: norwegian and english
  - pop ups should ideally show the lake name on top. Not sure this is available though?
- Terminology: on the web app, the terminology should be aimed more towards the user ("a hiker looking for a nice place to tent"). It is currently very developer oriented.
- Bug: The initial zoom should is currently south-east of norway (for the full map, not the akershus test). need to zoom out/pan to find the map.


### Round 4 - more polish

- "info" box should be a bit more elaborate. at least have a brief note on how they are calculated. AR5 data can download in a couple of different ways, but i often get a 400 error, so i believe that in practice, only a single type of data is downloaded.
- add a feature for embedding css and js into a single html file
  - update github action
- range slider for accessbility seems to work, but the appearance is inconsistent with the other sliders
- lake size should also be a range slider, and the upper bound should increase. might want to consider some super-linear scaling as well. should make it clearer that this is a filter, as opposed to a scoring dimension
- review js code for basic CS principles: dry, soc, kiss
- attributions: github link, proper attributions to sources
- check licenses and terms and conditions for data sources (double check that this web app can be published as a web site)
- the fish type list has a lot of spacing. this should be reduced
- consider using a light-weight ui library to make the appeareance more concise. i am open to a variety of suggestions, but i dont want a heavy framework that has a separate build/compilation step


### Round 5 - polish

- the range slider and "normal" sliders have different styles. their style should be unified.
- the upper bound on lake size needs to be increased. Also, the initial minimum size should be lower so that initial performance is better
- "cabin density" can have a maximum value of 0.15. 
- accessbility distance should have its minium value set to 0 instead of 200m
- selection of fish species should be a multi-select dropdown instead of individual boxes.

### Round 6 - terminology++

- Config.yaml for norway should ideally have a lower minimum lake size. Some small (but relevant) lakes are being excluded. This probably requires performance improvements, so consider if it is worth it for the MVP
- Legend:
  - No need for both title and subtitle. "Tegnforklaring" is a given
- "Poengberegning"
  - Re-order: accessbility -> urbanization -> cabin density -> fishing
  - Wording:
    - "Hyttetetthet" -> "Bygninger", and make it clear that this is a threshold concerning the number of buildings around a lake.
    - "Turens lengde" -> "tilgjengelighet", and add a label to the slider instead (i might want to extend this accessbility score later)
    - "Urbanisering" -> Something else. Perhaps "Bebyggelse".
    - Note that "hyttetetthet" and "urbanisering" are based on quite different data sources, and it needs to be clear that these are different scores.
    - "Innsjøstørrelse (filter)" - no need for "(filter)", i think it is clear that this is a filter. However, might want to move it to the bottom, and perhaps separate it from the scoring settings
    - "Poengberegning" is fine, but a bit long and wordy. "Scoring" on english is fine. Perhaps some other word is possible?
- Re-check "kildehenvisninger"
- Title

### Round 7 - polish

- Merge legend into "criteria" pane
- Use other defaults:
  - lake size filter maxed out (0-50km2)
  - cabin density and fishing toggled off
- reduce min lake size for norway by 50% (generate step)
- remove english in the web app
- re-color after slider has moved, and not while it is moving (current performance is not good enough for continuous update)

### Round 8 - clean up

This round is purely a clean-up round to remove dead code that is no longer relevant. This purpose is to make long-term maintainence easier

Some known issues that can be cleaned up
- remove most subcommands from the telttur module. only "generate" is used in practice
- remove "--skip-download" as a CLI option
- remove debugging code from app.js
- remove the "run telttur generate" error message from app.js
- clean up all config structures (config.py). many of these are no longer relevant, since the scoring functionality has been moved to app.js. moreover, all scoring-related data should always be computed, so no need for an option to toggle which scoring data is computed

### Round 9 - score consistency

Scoring is a bit inconsistent, i think. In general, i want lakes that fall within the ranges specified by the filters to get a perfect score. Outside the ranges, the score should taper. I want the following:
- accessbility/tilgjengelighet: "utmerket" within interval. "elendig" beyond 2x max and within 1/2 minimum
- "avstand fra bebyggelse": "utmerket" within the range. "elendig beyond 2x range
- cabin density is fine
- fishing is probably fine

I believe this is the most consistent way of handling this, but i am open to suggestions for improvement. Check the code and fix it to ensure consistent behavior. Also update dev/agent documentation and in-app descriptions where applicable

### Round 10 - improvements

Tracked in tasks 39–41.

- Add difference in vertical meters to "accessbility". Perhaps even evaluate the straight line between nearest point and lake → **task 39**
- Fishing should have a selector for two modes → **task 40**:
  - "Any fish is good" - i.e. an OR-filter approach. As long as any of the species are available, yield "Utmerket", otherwise, yield "Elendig".
  - "More is merrier" - almost like the current approach: if all species are present: "utmerket". if none are present: "elendig". if 1 or more is missing, "middels".
- add a distance indicator to the map → **task 41**

### Misc.

- Use a UI component framework to reduce the amount of javascript code. For ease of maintainence and readability
- Accessbility: distance from publid transportation