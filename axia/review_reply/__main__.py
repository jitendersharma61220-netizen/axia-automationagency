"""Command line: python -m axia.review_reply reviews.csv

reviews.csv columns: reviewer, rating, text (export from Google Business
Profile, or paste reviews into a sheet). Writes replies.csv next to it, ready
to paste into Google, and lists the unhappy customers to call first.
"""

import argparse
import csv
import os

from axia.ai import business_name, make_ai

from .replier import Review, handle


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.review_reply")
    p.add_argument("reviews_csv")
    p.add_argument("--out", default="replies.csv")
    args = p.parse_args(argv)

    ai = make_ai()
    business = business_name()
    phone = os.environ.get("AXIA_BUSINESS_PHONE", "")
    alerts = []
    with open(args.reviews_csv, newline="", encoding="utf-8") as f, \
            open(args.out, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["reviewer", "rating", "review", "sentiment", "call_customer", "reply"])
        for row in csv.DictReader(f):
            try:
                rating = int(float(row.get("rating") or 0))
            except ValueError:
                rating = 0
            review = Review(row.get("reviewer", ""), rating, row.get("text", ""))
            result = handle(review, business, ai, phone)
            w.writerow([review.reviewer, review.rating, review.text, result.sentiment,
                        "yes" if result.alert_owner else "", result.reply])
            if result.alert_owner:
                alerts.append(review)
    print(f"Replies written to {args.out}")
    for r in alerts:
        print(f"Call this customer: {r.reviewer} ({r.rating} stars): {r.text[:80]}")


if __name__ == "__main__":
    main()
