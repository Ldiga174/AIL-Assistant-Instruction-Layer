# Nostr as Future Decentralized Task Transport

GitHub Issues remain the default AIL 3.0 task queue.

Nostr is a future optional transport option only. It should not replace the
current GitHub Issue workflow in the AIL 3.0 MVP, and no runtime Nostr intake
is implemented in this repository yet.

## Concept

Nostr can represent task and result messages as signed events distributed
through relays. In a future AIL transport, a task could be published as a
signed event from a trusted owner public key. An executor could decode that
event into `.ail/inbox/current-task.md`, execute the bounded task under normal
AIL rules, then write `.ail/outbox/last-result.md` before publishing a signed
result event.

Relays are transport and distribution infrastructure. They are not authority.
Owner identity should be based on cryptographic keys and an explicit trusted
public key policy, not on the relay where an event appears.

## Future Mapping

```text
GitHub Issue        -> Nostr signed task event
Issue comment       -> Nostr signed result event
Issue labels        -> Nostr tags
Issue number        -> event id / task id
GitHub author       -> Nostr public key
.ail/inbox          -> local decoded task copy
.ail/outbox         -> local result before publish
```

## Safety Requirements

Executors must not execute arbitrary Nostr events automatically.

Any future Nostr intake must preserve AIL safety rules:

- verify the event signature before acting;
- verify that the signer public key is trusted for the project;
- treat relays as untrusted transport;
- expect spam and malformed events from public relays;
- require a bounded task, explicit scope, validation, and expected result;
- keep user or owner approval, or a narrow trusted-key policy, before execution;
- never store Nostr private keys in the repository;
- keep private key handling external and secure.

Relay presence is not authorization. A valid event from an untrusted key is not
an executable task.

## DPA Fit

This future transport fits longer-term DPA goals:

- decentralized task routing;
- agent coordination without a single platform dependency;
- censorship-resistant task and result distribution;
- portable owner identity based on public keys.

GitHub Issues remain the current reliable default until a Nostr design is
implemented, reviewed, and validated separately.
