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
  Icon,
  SimpleGrid,
  Spinner,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Textarea,
  Th,
  Thead,
  Tooltip,
  Tr,
  VStack,
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
} from '@chakra-ui/react';

import { runQuery } from '../api.js';

const PlayIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M8 5v14l11-7z"/>
  </Icon>
);

const SparkleIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2z"/>
  </Icon>
);

function ValueCell({ value }) {
  if (value === null || value === undefined) return <Text color="gray.400" fontStyle="italic">null</Text>;
  if (typeof value === 'object') return <Code fontSize="xs">{JSON.stringify(value)}</Code>;
  return <Text>{String(value)}</Text>;
}

export default function ChatTab({ goldenPrompts }) {
  const examples = useMemo(() => goldenPrompts || [], [goldenPrompts]);

  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [multiQuery, setMultiQuery] = useState(false);

  async function onSubmit() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runQuery(question.trim(), { 
        summarize: true, 
        includeRows: true,
        multiQuery: multiQuery,
      });
      setResult(res);
    } catch (e) {
      setError(e?.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box>
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={8} alignItems="start">
        <Box>
          <HStack mb={4} spacing={2}>
            <SparkleIcon boxSize={5} color="brand.500" />
            <Heading size="md">Ask a question</Heading>
          </HStack>

          <Box
            borderWidth="2px"
            borderColor="gray.200"
            borderRadius="xl"
            p={1}
            _focusWithin={{ borderColor: 'brand.400', shadow: 'md' }}
            transition="all 0.2s"
            bg="white"
          >
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g., Which team collected the most points in a single Premier League season?"
              minH="120px"
              border="none"
              _focus={{ boxShadow: 'none' }}
              resize="none"
              fontSize="md"
            />
          </Box>

          <HStack mt={4} spacing={4} wrap="wrap">
            <Button
              colorScheme="brand"
              onClick={onSubmit}
              isDisabled={loading || !question.trim()}
              leftIcon={<PlayIcon />}
              size="lg"
              px={8}
              shadow="md"
              _hover={{ shadow: 'lg', transform: 'translateY(-1px)' }}
              transition="all 0.2s"
            >
              Run Query
            </Button>
            
            <Tooltip 
              label="Generate 3 diverse SQL queries in parallel and cross-reference results for better accuracy"
              placement="top"
              hasArrow
              bg="gray.700"
            >
              <HStack 
                spacing={2} 
                bg={multiQuery ? 'purple.50' : 'gray.50'} 
                px={4} 
                py={2} 
                borderRadius="lg"
                cursor="pointer"
                onClick={() => setMultiQuery(!multiQuery)}
                transition="all 0.2s"
              >
                <Switch 
                  id="multi-query" 
                  isChecked={multiQuery} 
                  onChange={(e) => setMultiQuery(e.target.checked)}
                  colorScheme="purple"
                  size="md"
                />
                <Text fontSize="sm" color={multiQuery ? 'purple.700' : 'gray.600'} fontWeight={multiQuery ? 'semibold' : 'medium'}>
                  Multi-Query Mode
                </Text>
                {multiQuery && <Badge colorScheme="purple" variant="subtle" fontSize="xs">3x</Badge>}
              </HStack>
            </Tooltip>
            
            {loading && (
              <HStack color="gray.600">
                <Spinner size="sm" color="brand.500" />
                <Text fontSize="sm">{multiQuery ? 'Running 3 queries…' : 'Processing…'}</Text>
              </HStack>
            )}
          </HStack>

          <Divider my={6} />

          <Box>
            <Heading size="sm" mb={3} color="gray.700">
              💡 Try these examples
            </Heading>
            <VStack align="stretch" spacing={2}>
              {examples.map((x) => (
                <Button
                  key={x.question}
                  variant="ghost"
                  justifyContent="flex-start"
                  onClick={() => setQuestion(x.question)}
                  fontWeight="normal"
                  fontSize="sm"
                  color="gray.700"
                  bg="gray.50"
                  _hover={{ bg: 'brand.50', color: 'brand.700' }}
                  textAlign="left"
                  whiteSpace="normal"
                  height="auto"
                  py={3}
                  px={4}
                  borderRadius="lg"
                >
                  {x.question}
                </Button>
              ))}
            </VStack>
          </Box>
        </Box>

        <Box>
          <Heading size="md" mb={4}>Output</Heading>

          {error ? (
            <Alert status="error" borderRadius="xl" mb={4} shadow="sm">
              <Box>
                <AlertTitle fontWeight="semibold">Request failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Box>
            </Alert>
          ) : null}

          {!result ? (
            <Box
              borderWidth="2px"
              borderColor="gray.200"
              borderRadius="xl"
              p={8}
              bg="gray.50"
              textAlign="center"
            >
              <Text color="gray.500" fontSize="lg">
                Run a query to see the generated SQL, trace, and results.
              </Text>
            </Box>
          ) : (
            <VStack align="stretch" spacing={4}>
              {/* Summary Card */}
              <Box
                borderWidth="1px"
                borderRadius="xl"
                p={5}
                bg="gradient-to-br"
                bgGradient="linear(to-br, brand.50, white)"
                shadow="sm"
              >
                <HStack justify="space-between" mb={3}>
                  <Heading size="sm" color="brand.700">✨ Summary</Heading>
                  {typeof result.attempt_count === 'number' && (
                    <Badge
                      colorScheme={result.attempt_count > 1 ? 'orange' : 'green'}
                      variant="subtle"
                      px={2}
                      py={1}
                      borderRadius="full"
                    >
                      {result.attempt_count} attempt{result.attempt_count === 1 ? '' : 's'}
                    </Badge>
                  )}
                </HStack>
                <Text whiteSpace="pre-wrap" color="gray.700" lineHeight="tall">
                  {result.summary || '(no summary)'}
                </Text>
              </Box>

              {/* SQL Card */}
              <Box borderWidth="1px" borderRadius="xl" p={5} bg="white" shadow="sm">
                <Heading size="sm" mb={3} color="gray.700">
                  🔧 Generated SQL
                </Heading>
                <Box
                  overflowX="auto"
                  bg="gray.900"
                  borderRadius="lg"
                  p={4}
                >
                  <Code
                    whiteSpace="pre"
                    display="block"
                    bg="transparent"
                    color="green.300"
                    fontSize="sm"
                  >
                    {result.sql}
                  </Code>
                </Box>
              </Box>

              {Array.isArray(result.trace) && result.trace.length > 0 && (
                <Box borderWidth="1px" borderRadius="xl" p={5} bg="white" shadow="sm">
                  <HStack justify="space-between" mb={3}>
                    <Heading size="sm" color="gray.700">
                      🔍 Trace (LLM processing)
                    </Heading>
                    {result.queries_attempted ? (
                      <Badge colorScheme="purple">{result.queries_attempted} queries attempted</Badge>
                    ) : null}
                  </HStack>
                  <Accordion allowMultiple>
                    {result.trace.map((t, idx) => {
                      // Handle multi-query trace format
                      if (t.multi_query) {
                        return (
                          <AccordionItem key={`multi-${idx}`}>
                            <h2>
                              <AccordionButton>
                                <Box flex="1" textAlign="left">
                                  <HStack>
                                    <Badge colorScheme="purple">Multi-Query</Badge>
                                    <Badge colorScheme={t.successful > 0 ? 'green' : 'red'}>
                                      {t.successful}/{t.queries_attempted} succeeded
                                    </Badge>
                                  </HStack>
                                </Box>
                                <AccordionIcon />
                              </AccordionButton>
                            </h2>
                            <AccordionPanel>
                              <VStack align="stretch" spacing={3}>
                                {(t.results || []).map((qr, qrIdx) => (
                                  <Box key={qrIdx} borderWidth="1px" borderRadius="md" p={3} bg={qr.success ? 'green.50' : 'red.50'}>
                                    <HStack justify="space-between" mb={2}>
                                      <Text fontWeight="semibold">Query {qrIdx + 1}: {qr.approach}</Text>
                                      <HStack>
                                        <Badge colorScheme={qr.success ? 'green' : 'red'}>
                                          {qr.success ? 'Success' : 'Failed'}
                                        </Badge>
                                        {typeof qr.row_count === 'number' && (
                                          <Badge variant="subtle">rows: {qr.row_count}</Badge>
                                        )}
                                      </HStack>
                                    </HStack>
                                    <Text fontSize="sm" color="gray.600" mb={1}>
                                      Table: {qr.primary_table}
                                    </Text>
                                    {qr.error && (
                                      <Text color="red.600" fontSize="sm">{qr.error}</Text>
                                    )}
                                  </Box>
                                ))}
                              </VStack>
                            </AccordionPanel>
                          </AccordionItem>
                        );
                      }
                      
                      // Handle retry trace format (all_failed case)
                      if (t.all_failed) {
                        return (
                          <AccordionItem key={`retry-${idx}`}>
                            <h2>
                              <AccordionButton>
                                <Box flex="1" textAlign="left">
                                  <HStack>
                                    <Badge>Attempt {t.attempt}</Badge>
                                    <Badge colorScheme="orange">Retrying</Badge>
                                  </HStack>
                                </Box>
                                <AccordionIcon />
                              </AccordionButton>
                            </h2>
                            <AccordionPanel>
                              <Text fontWeight="semibold" mb={2}>All {t.queries_attempted} queries failed:</Text>
                              <VStack align="stretch" spacing={1}>
                                {(t.errors || []).map((err, errIdx) => (
                                  <Text key={errIdx} color="red.600" fontSize="sm">• {err}</Text>
                                ))}
                              </VStack>
                            </AccordionPanel>
                          </AccordionItem>
                        );
                      }
                      
                      // Handle standard single-query trace format
                      return (
                        <AccordionItem key={t.attempt || idx}>
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
                      );
                    })}
                  </Accordion>
                </Box>
              )}

              {/* Results Table */}
              <Box borderWidth="1px" borderRadius="xl" p={5} bg="white" shadow="sm">
                <Heading size="sm" mb={3} color="gray.700">
                  📊 Results
                </Heading>

                {result.retry_token && (
                  <Alert status="warning" borderRadius="lg" mb={4}>
                    <Box>
                      <AlertTitle fontWeight="semibold">Pipeline reported a retry token</AlertTitle>
                      <AlertDescription>{result.retry_reason}</AlertDescription>
                    </Box>
                  </Alert>
                )}

                <Box overflowX="auto" borderWidth="1px" borderRadius="lg" bg="gray.50">
                  <Table size="sm" variant="simple">
                    <Thead bg="gray.100">
                      <Tr>
                        {(result.columns || []).map((c) => (
                          <Th key={c} color="gray.700" fontSize="xs" textTransform="uppercase">{c}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {(result.rows || []).map((row, idx) => (
                        <Tr key={idx} _hover={{ bg: 'brand.50' }} transition="background 0.15s">
                          {(result.columns || []).map((c) => (
                            <Td key={`${idx}.${c}`} bg="white">
                              <ValueCell value={row?.[c]} />
                            </Td>
                          ))}
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>

                <Text color="gray.500" mt={3} fontSize="sm">
                  {Array.isArray(result.rows) ? result.rows.length : 0} row(s) returned (backend enforces a LIMIT).
                </Text>
              </Box>
            </VStack>
          )}
        </Box>
      </SimpleGrid>
    </Box>
  );
}
