# KENNY — multi-page concept store

Static trilingual footwear storefront (Chinese, Bahasa Melayu and English), with flag-labelled language choices. Start with `npm start` (port 3000). No build or dependency installation is needed to serve the website.

## Eight store pages

- `index.html`: brand homepage and campaign
- `shop.html`: catalogue, search, departments, audience views, outlet, wishlist and facets
- `product.html?id=aero-ice`: product details, size selection, image zoom, favourites and local demo reviews
- `story.html`: fictional demo factory narrative
- `craft.html`: design, materials and craft
- `cart.html`: persistent shopping bag, quantity updates and KENNY10 demo coupon
- `checkout.html`: demo delivery form, payment-method preview and order confirmation
- `contact.html`: support form and shipping/returns FAQ

Three additional legal pages (`cancellation-refunds.html`, `terms.html`, `privacy.html`) contain trilingual draft cancellation/refund rules, service terms and privacy information. All commercial terms remain illustrative until confirmed.

Seven independently generated product designs include a junior shoe with its own EU 28–35 size range. Adult models use EU 38–45. Product pages are selected by product ID rather than duplicating page files. Men and women show adult unisex products. Unstocked clothing, accessory or sport departments show an empty catalogue, never duplicated placeholder goods.

## Shared utilities

Accessible multi-column menus, mobile navigation, local favourites, demo member profiles and consent checkboxes, Google/Facebook/Apple sign-in previews, illustrative store filtering, help links, local demo order tracking, region/language preferences and privacy controls. No external identity, payment, logistics, analytics or advertising service is connected. Sign-in provider buttons explain that integration is pending; they never claim to log a customer in.

The flag-labelled language selector persists across pages. Copy is maintained in `i18n.js`; `translations.json` and `translations-ms.json` are readable source copies. Public social profile URLs belong in `social-links.js`; empty entries remain non-clickable.

KENNY10 applies a 10% demo discount. Shipping is RM 15, free when the discounted merchandise total reaches RM 500. No real payment or fulfilment occurs. No financial credentials are requested. Checkout/contact input is not saved or transmitted. Only voluntarily created profiles, favourites, reviews, bag lines, consent and demo order metadata are saved in localStorage. Final factory facts, specifications, legal copy, store locations and commercial policies need verification before real trading.

## Validation and deployment

`npm run check` validates scripts, all eleven page links and local assets, plus distinct image file content. `npm run test:browser` exercises the full cross-page flow with the cloud environment's supplied Playwright and `/usr/bin/chromium`. Start a local server on port 3010 first, or set `KENNY_TEST_URL` to the server root.

Pushes to `main` run `.github/workflows/deploy-pages.yml`. The workflow validates, uploads all eleven pages and assets, publishes through GitHub Pages and checks the published homepage. Repository Settings → Pages must allow GitHub Actions. The static artifact excludes development scripts, Git metadata and customer input.

The current visual direction uses a dark cinematic editorial theme in `cinema.css`, an independently generated campaign image, automatic floating motion and scroll-driven framing. No 3D model or arbitrary-angle product rotation is claimed. Reduced-motion preferences are respected.

Brand opening: `intro.js` and `intro.css` show a standalone, silent retro KENNY title animation before the store becomes interactive. It plays once per browser tab, lasts about three seconds, has no onscreen buttons, supports Escape, and uses a short static presentation for reduced-motion preferences. It does not change the storefront theme. Session data is used only to avoid replaying it on internal navigation.

Membership gating: `auth-demo.js` requires a local demo member session before adding to the bag and before checkout. It opens registration automatically, resumes the pending action after registration, and offers one-click local demo login for a returning profile. Sessions last for the current tab; the voluntary demo profile can remain in this browser. This is not secure authentication, does not verify email or identity and is not suitable as a real account or payment gate. A production identity provider is still required for real or cross-device accounts.

Readable type: navigation, catalogue copy, forms and policy paragraphs use larger font sizes, with responsive handling for longer Malay text.

Motion: `motion.css` and `motion.js` provide small product float, slow ambient lighting, staged hero copy, staggered catalogue cards and panel transitions. Hero position stays independent of these effects. Motion begins after the intro, pauses offscreen/in hidden tabs, and follows the system reduced-motion preference.

Airflow lighting (`airflow.js`): mouse hover, taps, finger movement and native page scrolling create curved fluorescent wisps on a pointer-transparent canvas. Trails fade in about one second; form fields and the brand opening do not trigger them. The effect uses passive listeners, stops when idle, and is disabled for reduced motion.

Airflow assets use an explicit URL version so browsers request the movement-driven implementation instead of an older click-ray file. Mouse hover uses `mousemove` independently of button state, and wheel plus capture-phase nested-scroll listeners also emit trails.
