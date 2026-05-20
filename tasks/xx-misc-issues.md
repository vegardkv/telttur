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

### Known issues to fix later

- Popup labels does not reflect interactively changed values. 
- min lake size should probably be hidden? want to perhaps dynamically reduce the number of shown markers based on zoom level
- When the final layout has been determined:
  - Minimize the amount of javascript (for maintainability)
    - I believe a lot of the scoring mechanisms can be handled differently. Ideally, no logic should be necessary in JavaScript. Threshold checks should suffice.
  - But keep in mind performance
  - Pre-compute data if possible
  - But be wary of the national scale file size
    - Perhaps necessary to split into a json file and an html file
