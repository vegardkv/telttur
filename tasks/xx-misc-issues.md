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


### Known issues to fix later

- "scoring" on the python side no longer make sense. However, each "scoring" submodule still is relevant for how javascript calculates the various scores. Should consider some refactoring to clarify responsibility

- epsg codes for utm33 is spread all over. might want to move to common.py
- buffer_roads function uses hard-coded strings for column names. 