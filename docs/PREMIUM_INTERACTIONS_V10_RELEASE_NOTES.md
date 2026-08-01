# Authentic AI — Premium Interactions V10

## Scope

Premium Interactions V10 upgrades the chat composer, Sherry launch feedback, document-generation progress, and artifact-result reveal without changing backend artifact contracts.

## Composer

- Compact single-row action layout instead of a tall empty composer.
- Auto-growing textarea up to 220 px on desktop and 180 px on mobile.
- Attach, prompt, Sherry, and send controls remain aligned while multiline content grows upward.
- More descriptive Serenya placeholder.
- Mobile Sherry control is preserved except on extremely narrow screens.

## Document generation

- Dedicated orbital activity visual.
- Progress labels are derived from real backend job state and stage text.
- Five visible workflow phases: Understand, Organise, Render, Compose, Verify.
- Existing percentage, progress bar, and cancellation remain functional.
- Completed artifact cards use a restrained result-reveal animation.

## Sherry

- Clicking Sherry now shows a short premium launch animation before opening the existing voice workspace.
- The UI says “Opening Sherry” rather than claiming that the microphone is listening before a real voice session exists.
- Reduced-motion preferences are respected.

## Boundaries

This release does not implement microphone transport, speech recognition, or voice-session state. Those states must be connected to real Sherry session events before labels such as Listening, Understanding, or Speaking are displayed.
