# KENNY concept store

Static frontend sportswear store. Run `npm start` from this directory, then open port 3000.

Features: responsive product catalogue, search/filter/sort, product details, EU sizes, persistent local shopping bag, quantity editing, demo checkout and order confirmation. Currency: MYR. No backend, payment, inventory, email service or real order fulfilment is connected. Product names, prices and performance specifications are illustrative. Customer checkout data is not persisted or sent to a server. Only product IDs, sizes and quantities are saved in localStorage.

Product campaign image was generated for this concept. The catalogue contains six separately generated shoe designs with distinct image files. The hero campaign is a separate image; the technology section uses an original vector illustration. Replace the demo catalogue with genuine product photography and verified specifications before commercial launch. The reference videos are not included in the website.

Checks: `npm run check`. Browser checks cover filters, mandatory size selection, quantity updates, totals, checkout, empty bag, and mobile overflow.

Language: use the header 中文 / EN toggle. The selection is saved locally. Translations live in `i18n.js`; update both languages when editing copy. `translations.json` is a readable copy of the initial dictionary.

Social profiles: edit the five empty HTTPS URL fields in `social-links.js`. Unconfigured logos remain non-clickable; no fake profile URLs are used.

Factory story: the current narrative is fictional demo copy, approved for preview. Confirm real history, team, production details and claims before commercial launch.
