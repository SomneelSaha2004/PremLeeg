import React from 'react';
import {
  Box,
  Code,
  Heading,
  ListItem,
  OrderedList,
  Text,
} from '@chakra-ui/react';

export default function ArchitectureTab() {
  return (
    <Box>
      <Heading size="md" mb={3}>
        Project architecture
      </Heading>

      <Text color="gray.700" mb={4}>
        Your backend is designed as a small “SQL agent” pipeline that turns a natural-language question into a safe,
        validated SQL query, executes it, and optionally synthesizes a summary.
      </Text>

      <OrderedList spacing={2} color="gray.700">
        <ListItem>
          <strong>Frontend</strong> sends a question to <Code>/api/query</Code>.
        </ListItem>
        <ListItem>
          <strong>Intent + hints</strong>: the pipeline classifies the question and adds lightweight hints (e.g. streak views,
          team-name normalization).
        </ListItem>
        <ListItem>
          <strong>Prompting</strong>: constructs a SQL-generation prompt using a compact schema snapshot.
        </ListItem>
        <ListItem>
          <strong>LLM SQL generation</strong>: model proposes SQL.
        </ListItem>
        <ListItem>
          <strong>Validation + patching</strong>: enforces SELECT-only, allowed tables/columns, limits, and guardrails.
        </ListItem>
        <ListItem>
          <strong>Execution</strong>: runs the SQL against Postgres and returns rows/columns.
        </ListItem>
        <ListItem>
          <strong>Answer synthesis</strong>: optionally generates a natural-language summary from the query + results.
        </ListItem>
      </OrderedList>

      <Box mt={6} borderWidth="1px" borderRadius="md" p={4}>
        <Heading size="sm" mb={2}>
          Robustness features shown in this demo
        </Heading>
        <Text color="gray.700">
          The Chat tab displays a “Trace” section that shows retries (e.g. validation warnings or empty results) so you can
          see how the agent iterates before returning a final answer.
        </Text>
      </Box>
    </Box>
  );
}
