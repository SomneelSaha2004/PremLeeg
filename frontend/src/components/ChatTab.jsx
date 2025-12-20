import React, { useMemo, useState } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Box,
  Button,
  Code,
  Divider,
  Heading,
  HStack,
  SimpleGrid,
  Spinner,
  Table,
  Tbody,
  Td,
  Text,
  Textarea,
  Th,
  Thead,
  Tr,
  VStack,
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
} from '@chakra-ui/react';

import { runQuery } from '../api.js';

function ValueCell({ value }) {
  if (value === null || value === undefined) return <Text color="gray.500">null</Text>;
  if (typeof value === 'object') return <Code>{JSON.stringify(value)}</Code>;
  return <Text>{String(value)}</Text>;
}

export default function ChatTab({ goldenPrompts }) {
  const examples = useMemo(() => goldenPrompts || [], [goldenPrompts]);

  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function onSubmit() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runQuery(question.trim(), { summarize: true, includeRows: true });
      setResult(res);
    } catch (e) {
      setError(e?.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} alignItems="start">
        <Box>
          <Heading size="md" mb={3}>
            Ask a question
          </Heading>

          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g., Which team collected the most points in a single Premier League season?"
            minH="130px"
          />

          <HStack mt={3}>
            <Button colorScheme="blue" onClick={onSubmit} isDisabled={loading || !question.trim()}>
              Run
            </Button>
            {loading ? (
              <HStack>
                <Spinner size="sm" />
                <Text>Processing…</Text>
              </HStack>
            ) : null}
          </HStack>

          <Divider my={6} />

          <Heading size="sm" mb={2}>
            Common queries (examples)
          </Heading>
          <Text color="gray.600" mb={3}>
            Click one to populate the input.
          </Text>
          <VStack align="stretch" spacing={2}>
            {examples.map((x) => (
              <Button
                key={x.question}
                variant="outline"
                justifyContent="flex-start"
                onClick={() => setQuestion(x.question)}
              >
                {x.question}
              </Button>
            ))}
          </VStack>
        </Box>

        <Box>
          <Heading size="md" mb={3}>
            Output
          </Heading>

          {error ? (
            <Alert status="error" borderRadius="md" mb={4}>
              <Box>
                <AlertTitle>Request failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Box>
            </Alert>
          ) : null}

          {!result ? (
            <Box borderWidth="1px" borderRadius="md" p={4}>
              <Text color="gray.600">Run a query to see the generated SQL, trace, and results.</Text>
            </Box>
          ) : (
            <VStack align="stretch" spacing={4}>
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <HStack justify="space-between" mb={2}>
                  <Heading size="sm">Summary</Heading>
                  {typeof result.attempt_count === 'number' ? (
                    <Badge colorScheme={result.attempt_count > 1 ? 'orange' : 'green'}>
                      {result.attempt_count} attempt{result.attempt_count === 1 ? '' : 's'}
                    </Badge>
                  ) : null}
                </HStack>
                <Text whiteSpace="pre-wrap">{result.summary || '(no summary)'}</Text>
              </Box>

              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Heading size="sm" mb={2}>
                  Generated SQL
                </Heading>
                <Box overflowX="auto">
                  <Code whiteSpace="pre">{result.sql}</Code>
                </Box>
              </Box>

              {Array.isArray(result.trace) && result.trace.length > 0 ? (
                <Box borderWidth="1px" borderRadius="md" p={4}>
                  <Heading size="sm" mb={2}>
                    Trace (LLM processing)
                  </Heading>
                  <Accordion allowMultiple>
                    {result.trace.map((t) => (
                      <AccordionItem key={t.attempt}>
                        <h2>
                          <AccordionButton>
                            <Box flex="1" textAlign="left">
                              <HStack>
                                <Badge>Attempt {t.attempt}</Badge>
                                <Badge colorScheme={t.outcome === 'success' ? 'green' : t.outcome === 'retry' ? 'orange' : 'red'}>
                                  {t.outcome}
                                </Badge>
                                {typeof t.row_count === 'number' ? (
                                  <Badge variant="subtle">rows: {t.row_count}</Badge>
                                ) : null}
                              </HStack>
                            </Box>
                            <AccordionIcon />
                          </AccordionButton>
                        </h2>
                        <AccordionPanel>
                          {t.retry_reason ? (
                            <Box mb={3}>
                              <Text fontWeight="semibold">Reason</Text>
                              <Text color="gray.700" whiteSpace="pre-wrap">{t.retry_reason}</Text>
                            </Box>
                          ) : null}

                          {t.warning ? (
                            <Box mb={3}>
                              <Text fontWeight="semibold">Warning</Text>
                              <Text color="orange.700" whiteSpace="pre-wrap">{t.warning}</Text>
                            </Box>
                          ) : null}

                          {t.error ? (
                            <Box mb={3}>
                              <Text fontWeight="semibold">Error</Text>
                              <Text color="red.700" whiteSpace="pre-wrap">{t.error}</Text>
                            </Box>
                          ) : null}

                          {t.raw_sql ? (
                            <Box mb={3}>
                              <Text fontWeight="semibold">Raw SQL</Text>
                              <Box overflowX="auto">
                                <Code whiteSpace="pre">{t.raw_sql}</Code>
                              </Box>
                            </Box>
                          ) : null}

                          {t.validated_sql ? (
                            <Box>
                              <Text fontWeight="semibold">Validated SQL</Text>
                              <Box overflowX="auto">
                                <Code whiteSpace="pre">{t.validated_sql}</Code>
                              </Box>
                            </Box>
                          ) : null}
                        </AccordionPanel>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </Box>
              ) : null}

              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Heading size="sm" mb={2}>
                  Result
                </Heading>

                {result.retry_token ? (
                  <Alert status="warning" borderRadius="md" mb={3}>
                    <Box>
                      <AlertTitle>Pipeline reported a retry token</AlertTitle>
                      <AlertDescription>{result.retry_reason}</AlertDescription>
                    </Box>
                  </Alert>
                ) : null}

                <Box overflowX="auto" borderWidth="1px" borderRadius="md">
                  <Table size="sm">
                    <Thead>
                      <Tr>
                        {(result.columns || []).map((c) => (
                          <Th key={c}>{c}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {(result.rows || []).map((row, idx) => (
                        <Tr key={idx}>
                          {(result.columns || []).map((c) => (
                            <Td key={`${idx}.${c}`}>
                              <ValueCell value={row?.[c]} />
                            </Td>
                          ))}
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>

                <Text color="gray.600" mt={2}>
                  {Array.isArray(result.rows) ? result.rows.length : 0} row(s) shown (backend enforces a LIMIT).
                </Text>
              </Box>
            </VStack>
          )}
        </Box>
      </SimpleGrid>
    </Box>
  );
}
