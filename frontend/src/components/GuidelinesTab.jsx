import React, { useMemo } from 'react';
import { Badge, Box, Code, Heading, HStack, Icon, ListItem, SimpleGrid, Text, UnorderedList, VStack } from '@chakra-ui/react';

const TipIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
  </Icon>
);

const SparklesIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2z"/>
  </Icon>
);

export default function GuidelinesTab({ goldenPrompts }) {
  const examples = useMemo(() => goldenPrompts || [], [goldenPrompts]);

  return (
    <Box>
      <HStack mb={6} spacing={2}>
        <TipIcon boxSize={6} color="brand.500" />
        <Heading size="md" color="gray.800">Query Guidelines</Heading>
      </HStack>

      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} mb={8}>
        <Box
          p={5}
          borderWidth="1px"
          borderRadius="xl"
          bg="white"
          shadow="sm"
          _hover={{ shadow: 'md' }}
          transition="shadow 0.2s"
        >
          <Heading size="sm" mb={4} color="gray.700">📝 Writing Good Queries</Heading>
          <VStack align="stretch" spacing={3}>
            <Box p={3} bg="gray.50" borderRadius="lg">
              <Text fontSize="sm" color="gray.700">
                <strong>Be specific</strong> about entity (team/player), metric (goals, points, cards), and scope (season vs all-time).
              </Text>
            </Box>
            <Box p={3} bg="gray.50" borderRadius="lg">
              <Text fontSize="sm" color="gray.700">
                For season records, say <Code fontSize="xs">"in a single Premier League season"</Code>
              </Text>
            </Box>
            <Box p={3} bg="gray.50" borderRadius="lg">
              <Text fontSize="sm" color="gray.700">
                For streaks, use: <Code fontSize="xs">"winning streak"</Code>, <Code fontSize="xs">"unbeaten run"</Code>, <Code fontSize="xs">"clean sheet streak"</Code>
              </Text>
            </Box>
            <Box p={3} bg="gray.50" borderRadius="lg">
              <Text fontSize="sm" color="gray.700">
                Want ties? Ask to <Code fontSize="xs">"return all ties"</Code>
              </Text>
            </Box>
          </VStack>
        </Box>

        <Box
          p={5}
          borderWidth="2px"
          borderColor="purple.200"
          borderRadius="xl"
          bgGradient="linear(to-br, purple.50, white)"
          shadow="sm"
        >
          <HStack mb={4} spacing={2}>
            <SparklesIcon boxSize={5} color="purple.500" />
            <Heading size="sm" color="purple.700">Multi-Query Mode</Heading>
            <Badge colorScheme="purple" variant="solid" fontSize="xs">NEW</Badge>
          </HStack>
          <Text color="gray.700" mb={4} fontSize="sm">
            Enable the toggle for improved accuracy on complex questions.
          </Text>
          <VStack align="stretch" spacing={2}>
            <HStack spacing={2} p={2} bg="white" borderRadius="md">
              <Badge colorScheme="purple" variant="subtle">1</Badge>
              <Text fontSize="sm" color="gray.600">Generates 3 diverse SQL approaches</Text>
            </HStack>
            <HStack spacing={2} p={2} bg="white" borderRadius="md">
              <Badge colorScheme="purple" variant="subtle">2</Badge>
              <Text fontSize="sm" color="gray.600">Runs queries in parallel (10s timeout)</Text>
            </HStack>
            <HStack spacing={2} p={2} bg="white" borderRadius="md">
              <Badge colorScheme="purple" variant="subtle">3</Badge>
              <Text fontSize="sm" color="gray.600">Cross-references for best answer</Text>
            </HStack>
          </VStack>
        </Box>
      </SimpleGrid>

      <Box>
        <Heading size="sm" mb={4} color="gray.700">
          💡 Example Questions
        </Heading>
        <VStack align="stretch" spacing={2}>
          {examples.map((x, idx) => (
            <Box
              key={x.question}
              p={4}
              borderWidth="1px"
              borderRadius="lg"
              bg="white"
              _hover={{ bg: 'brand.50', borderColor: 'brand.200' }}
              transition="all 0.2s"
              cursor="default"
            >
              <HStack spacing={3}>
                <Badge
                  colorScheme="brand"
                  variant="subtle"
                  borderRadius="full"
                  px={2}
                  py={1}
                  fontSize="xs"
                >
                  {idx + 1}
                </Badge>
                <Text fontWeight="medium" color="gray.800">{x.question}</Text>
              </HStack>
              {x.tests && (
                <Text fontSize="sm" color="gray.500" mt={2} ml={10}>
                  {x.tests}
                </Text>
              )}
            </Box>
          ))}
        </VStack>
      </Box>
    </Box>
  );
}
