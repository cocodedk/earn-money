"use strict";
const express = require("express");

const fixation = require("./routes/fixation");
const rotation = require("./routes/rotation");
const invalidation = require("./routes/invalidation");
const lifetime = require("./routes/lifetime");

const app = express();

app.use(express.urlencoded({ extended: false }));
app.use(express.json());

app.use("/fixation", fixation);
app.use("/rotation", rotation);
app.use("/invalidation", invalidation);
app.use("/lifetime", lifetime);

app.get("/healthz", (_req, res) => res.json({ status: "ok" }));

const PORT = parseInt(process.env.PORT || "3000", 10);
app.listen(PORT, () => {
  console.log(`session-lifecycle-lab listening on :${PORT}`);
});
