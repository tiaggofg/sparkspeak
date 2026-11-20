INSERT INTO decks (slug, name, description, target_cefr, persona_prompt)
VALUES
    (
        'conversational',
        'Everyday & Small Talk',
        'Natural daily conversations, small talk, opinions, and storytelling.',
        'B2',
        'You are a friendly native-speaking colleague chatting over coffee. Keep turns natural and concise.'
    ),
    (
        'phrasal-verbs',
        'High-Frequency Phrasal Verbs',
        'Essential English phrasal verbs used in everyday and engineering contexts.',
        'B2',
        'You are an encouraging English coach drilling practical phrasal verbs in realistic contexts.'
    ),
    (
        'tech-meetings',
        'Tech Meetings',
        'Software engineering dailies, architecture reviews, RFC debates, and incident calls.',
        'B2',
        'You are a Senior Staff Engineer collaborating in standups, RFC reviews, and production incident calls.'
    )
ON CONFLICT (slug) DO NOTHING;

-- Starter cards for conversational
INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'How do you politely ask someone to repeat what they just said?',
       'how do you politely ask someone to repeat what they just said',
       'Could you say that again? / Sorry, I did not catch that.',
       'Sorry, I did not catch that — could you say it one more time?',
       'vocab',
       'seed'
FROM decks WHERE slug = 'conversational'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'How do you say you are looking forward to the weekend?',
       'how do you say you are looking forward to the weekend',
       'I am really looking forward to the weekend.',
       'It has been a busy week, so I am looking forward to the weekend.',
       'grammar_fix',
       'seed'
FROM decks WHERE slug = 'conversational'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

-- Starter cards for phrasal-verbs
INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'To delay or postpone an event (phrasal verb with ''put'')',
       'to delay or postpone an event phrasal verb with put',
       'put off',
       'We had to put off the deployment until Monday.',
       'phrasal_verb',
       'seed'
FROM decks WHERE slug = 'phrasal-verbs'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'To investigate or examine a problem carefully (phrasal verb with ''look'')',
       'to investigate or examine a problem carefully phrasal verb with look',
       'look into',
       'I will look into the latency spike right after standup.',
       'phrasal_verb',
       'seed'
FROM decks WHERE slug = 'phrasal-verbs'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'To find a solution or understand something (phrasal verb with ''figure'')',
       'to find a solution or understand something phrasal verb with figure',
       'figure out',
       'We finally figured out why the migration was failing.',
       'phrasal_verb',
       'seed'
FROM decks WHERE slug = 'phrasal-verbs'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

-- Starter cards for tech-meetings
INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'Give a concise standup update explaining you are blocked by an upstream API review.',
       'give a concise standup update explaining you are blocked by an upstream api review',
       'I am currently blocked on the upstream API review, so I am picking up another ticket meanwhile.',
       'Yesterday I finished the auth tests; today I am blocked on the API review.',
       'tech_scenario',
       'seed'
FROM decks WHERE slug = 'tech-meetings'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;

INSERT INTO cards (deck_id, front_prompt, normalized_front, back_reference, context_example, card_type, source_type)
SELECT id,
       'Politely push back on an architecture proposal due to operational complexity.',
       'politely push back on an architecture proposal due to operational complexity',
       'I see the benefit, though I am concerned about the operational overhead it introduces.',
       'Could we start with a simpler approach before adding a separate queue?',
       'tech_scenario',
       'seed'
FROM decks WHERE slug = 'tech-meetings'
ON CONFLICT (deck_id, normalized_front) DO NOTHING;
