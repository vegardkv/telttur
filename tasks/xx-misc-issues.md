Misc clean-up issues:
- Markers should be inside the polygon instead of centroid
- Use Colors in popup to indicate scores? (hard to read)
- I think there is a mismatch with interactivity and clustering. For now, i should focus on the non-clustering variant.
- Cluster colors are a bit hard to interpret. Not sure what they mean. Should perhaps reflect the "mode" for the suitability?

I am working towards the first viable model. It is starting to take proper shape. I think the following should be the first version:
- No clustering (seems to have some interaction bugs with interactivity controls)
- Interactivity on, but some adjustments are needed:
  - accessbility should have a two-sided range slider instead. within the range will be considered excellent. beyond 2x max range is terrible, and use some reasonable stepping in-between. Below the min range, less than half the range is terrible, and do a similar stepping in-between. if two-sided slider is difficult, to separate sliders is ok.
- National scale - will try performance and assess if it is good enough.
- the ar5 layer should not be added to the map
- no toggle for base map (use greyscale for now)
- Marker should be inside the polygon instead of centroid. It looks weird if the marker is outside the lake
- If easy: show scoring labels with colors in the popup. (a bit hard to interpret why a specific lake gets its score)
