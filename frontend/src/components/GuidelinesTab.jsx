import React, { useMemo } from 'react';
import { Box, Code, Heading, ListItem, Text, UnorderedList, VStack } from '@chakra-ui/react';

export default function GuidelinesTab({ goldenPrompts }) {
  const examples = useMemo(() => goldenPrompts || [], [goldenPrompts]);

  return (
    <Box>
      <Heading size="md" mb={3}>
        Query guidelines
      </Heading>

      <UnorderedList spacing={2} color="gray.700">
        <ListItem>
          Be specific about <strong>entity</strong> (team/player), <strong>metric</strong> (goals, points, cards), and
          <strong> scope</strong> (single season vs all-time).
        </ListItem>
        <ListItem>
          If you mean a season record, say <Code>"in a single Premier League season"</Code>.
        </ListItem>
        <ListItem>
          For streaks, ask explicitly for <Code>"winning streak"</Code>, <Code>"unbeaten run"</Code>, <Code>"clean sheet streak"</Code>, etc.
        </ListItem>
        <ListItem>
          If you want ties included, ask for <Code>"return all ties"</Code>.
        </ListItem>
      </UnorderedList>

      <Box mt={6}>
        <Heading size="sm" mb={2}>
          Example questions
        </Heading>
        <Text color="gray.600" mb={3}>
          These mirror the first few golden prompts.
        </Text>
        <VStack align="stretch" spacing={2}>
          {examples.map((x) => (
            <Box key={x.question} borderWidth="1px" borderRadius="md" p={3}>
              <Text fontWeight="semibold">{x.question}</Text>
              {x.tests ? <Text color="gray.600">{x.tests}</Text> : null}
            </Box>
          ))}
        </VStack>
      </Box>
    </Box>
  );
}
