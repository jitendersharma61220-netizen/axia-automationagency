"""Command line: python -m axia.whatsapp_reply <command>"""

import argparse
import os

from axia.ai import business_name, make_ai

from . import bot, whatsapp


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.whatsapp_reply")
    p.add_argument("--faq", default=os.environ.get("AXIA_FAQ_PATH", "examples/faq_clinic.txt"))
    sub = p.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="test how the bot answers one message")
    ask.add_argument("message")
    srv = sub.add_parser("serve", help="start the WhatsApp webhook")
    srv.add_argument("--port", type=int, default=8001)

    args = p.parse_args(argv)
    env = os.environ
    faq = bot.load_faq(args.faq)
    ai = make_ai(env)
    business = business_name(env)

    if args.cmd == "ask":
        reply = bot.answer(faq, args.message, business, ai)
        print(reply.text)
        if reply.handoff:
            print("(handed to the owner)")
    elif args.cmd == "serve":
        handler = whatsapp.make_handler(
            faq, whatsapp.make_sender(env), business,
            env.get("AXIA_WA_VERIFY_TOKEN", ""), ai, env.get("AXIA_OWNER_WHATSAPP", ""),
        )
        whatsapp.serve(handler, port=args.port)


if __name__ == "__main__":
    main()
