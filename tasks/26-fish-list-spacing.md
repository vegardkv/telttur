# Task 26 – Reduce fish type list spacing

## Goal

Reduce the excessive vertical spacing in the fishing genera checkbox list in the control panel.

## Problem

The fish type checkboxes (trout, char, grayling, pike, etc.) in the Fishing scoring card have too much vertical spacing between items, making the card unnecessarily tall. This is because each checkbox `<label>` is rendered as a block element followed by a `<br>`, and the default card label styling adds margin.

## Fix

- Remove the `<br>` tags between fish genera checkboxes in `buildControls()` (or switch to a different layout approach)
- Add CSS to reduce spacing between the checkbox labels specifically within the fishing card body
- Consider using `display: flex; flex-wrap: wrap` or tighter `line-height` / `margin` for the fish list

Target: each checkbox item should have ~2–3px vertical gap, similar to a compact list.

## Files to modify

- [web/app.js](../web/app.js) — fish genera checkbox HTML generation in `buildControls()`
- [web/style.css](../web/style.css) — spacing rules for fish list items

## Acceptance criteria

- Fish genera list is compact with minimal spacing
- Checkboxes remain clickable and readable
- No visual regression in other cards
