import express from "express";
import fetch from "node-fetch";
import bodyParser from "body-parser";
import dotenv from "dotenv";
dotenv.config();

const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 5000;
const CLIENT_ID = process.env.PAYPAL_CLIENT_ID;
const CLIENT_SECRET = process.env.PAYPAL_SECRET;

app.post("/paypal/create-order", async (req, res) => {
  const { amount, currency } = req.body;

  const accessToken = await fetch("https://api-m.sandbox.paypal.com/v1/oauth2/token", {
    method: "POST",
    headers: {
      Authorization: "Basic " + Buffer.from(CLIENT_ID + ":" + CLIENT_SECRET).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  }).then((res) => res.json());

  const order = await fetch("https://api-m.sandbox.paypal.com/v2/checkout/orders", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken.access_token}`,
    },
    body: JSON.stringify({
      intent: "CAPTURE",
      purchase_units: [{ amount: { currency_code: currency, value: amount } }],
    }),
  }).then((res) => res.json());
import express from "express";
import bodyParser from "body-parser";
const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 4000;

// ⚙️ अपने UPI ID डालो:
const UPI_ID = "your-upi-id@okaxis"; // <-- यहाँ अपना actual UPI ID डालो
const NAME = "Omniverse AI Supreme"; // display name

app.post("/gpay/link", (req, res) => {
  const { amount, note } = req.body;
  const upiLink = `upi://pay?pa=${UPI_ID}&pn=${encodeURIComponent(NAME)}&am=${amount}&cu=INR&tn=${encodeURIComponent(note || "Payment to Omniverse")}`;
  res.json({ link: upiLink });
});

app.listen(PORT, () => console.log(`✅ GPay/UPI Server running on port ${PORT}`));
PAYPAL_CLIENT_ID
PAYPAL_SECRET
name: Omniverse Payments

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      PAYPAL_CLIENT_ID: ${{ secrets.PAYPAL_CLIENT_ID }}
      PAYPAL_SECRET: ${{ secrets.PAYPAL_SECRET }}

    steps:
      - name: Checkout Repo
        uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install Dependencies
        run: npm install express node-fetch body-parser dotenv

      - name: Start PayPal + GPay servers
        run: |
          nohup node payments/paypal-server.js &
          nohup node payments/gpay-server.js &
          echo "🚀 Servers launched successfully"


  res.json(order);
});

app.listen(PORT, () => console.log(`✅ PayPal Server running on port ${PORT}`));


