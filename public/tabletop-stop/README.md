# Tabletop Stop — photos & videos

Drop your image files in this folder, then point to them from
`app/tabletop-stop/content.js`.

Example:

```js
{
  id: "harvest-dinner-plate",
  name: "Harvest Dinner Plate in Terracotta & Cream, Set of 4",
  image: "/tabletop-stop/harvest-plate.jpg",        // product shot on white
  hoverImage: "/tabletop-stop/harvest-plate-table.jpg", // styled shot shown on hover
  ...
}
```

Tips
- Product shots: square (1:1), at least 1200 × 1200 px, on a white or pale background.
- Styled / lifestyle shots: same size works; they are shown when a shopper hovers.
- Gallery images: any size; the first and sixth tiles are tall, so portrait shots look best there.
- Hero, About and "Shop the Look" images: landscape or portrait, at least 1600 px on the long side.
- Keep file sizes under ~500 KB each (export as JPG at 80% quality, or WebP).

Videos
- Upload to YouTube (unlisted is fine) and paste the video ID into `videos[].youtubeId`,
  or put an .mp4 in this folder and set `videos[].src` to `/tabletop-stop/your-video.mp4`.
