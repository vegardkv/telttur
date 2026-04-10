I want to create a map which shows suitable camping locations in Norway.

I want the following features:
- Around all available roads, add a buffer zone of X meters and visualize the polygon. The will represent the distance I am willing to walk from the car. Start with a simple buffer. Future extensions: combine with path planning and knowledge of parking possitilies as well. Another extension: different color shade depending on road type ("riksvei" vs smaller local roads)
- Show all lakes as colored polygons, so that it is easy to see whether a lake overlaps with the distance from road I am willing to walk. Lakes should be classified according to camping suitability. This needs further investigation, but key metrics could be: house/cabin density around the lake or "steepness" around the lake (i.e. probabilitiy of finding a flat spot for tenting)
- Some visualization possibility for showing the area type (urban, forest, mountain, etc.)

As a first version, I just want something that works. E.g. this can be a generated html file that needs to be re-created if I change any of the input parameters. Long term, I might want to turn this into a proper web site.

I want you to do the following:
- Suggest and specify a tech stack
- Investigate which data are openly available, and how to fetch them

Lets discuss these first, and once they have been established, I want you to create sub-tasks to complete this implementation. Create the tasks in a dedicated folder, with one document (.md) for each task. I'll most likely dedicate all tasks to an AI agent.
