import React from 'react';
import {
  Badge,
  Box,
  Code,
  Heading,
  HStack,
  Icon,
  SimpleGrid,
  Text,
  VStack,
} from '@chakra-ui/react';

const PipelineIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M22 9V7h-2V5c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-2h2v-2h-2v-2h2v-2h-2V9h2zm-4 10H4V5h14v14z"/>
  </Icon>
);

const SparklesIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2z"/>
  </Icon>
);

const DatabaseIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4z"/>
  </Icon>
);

const ShieldIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
  </Icon>
);

function PipelineStep({ number, title, description, color = "brand" }) {
  return (
    <HStack spacing={3} align="start">
      <Box
        bg={`${color}.500`}
        color="white"
        borderRadius="full"
        w={7}
        h={7}
        display="flex"
        alignItems="center"
        justifyContent="center"
        fontSize="sm"
        fontWeight="bold"
        flexShrink={0}
      >
        {number}
      </Box>
      <Box>
        <Text fontWeight="semibold" color="gray.800" fontSize="sm">{title}</Text>
        <Text color="gray.600" fontSize="sm">{description}</Text>
      </Box>
    </HStack>
  );
}

export default function ArchitectureTab() {
  return (
    <Box>
      <HStack mb={6} spacing={2}>
        <PipelineIcon boxSize={6} color="brand.500" />
        <Heading size="md" color="gray.800">System Architecture</Heading>
      </HStack>

      <Text color="gray.600" mb={8} fontSize="md" maxW="3xl">
        PremLeeg uses an AI-powered SQL agent pipeline that converts natural language questions into validated SQL queries.
        It supports two execution modes for different accuracy/speed tradeoffs.
      </Text>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} mb={8}>
        {/* Standard Pipeline */}
        <Box
          p={6}
          borderWidth="1px"
          borderRadius="xl"
          bg="white"
          shadow="sm"
        >
          <HStack mb={5} spacing={2}>
            <Box p={2} bg="brand.100" borderRadius="lg">
              <PipelineIcon boxSize={5} color="brand.600" />
            </Box>
            <Box>
              <Heading size="sm" color="gray.800">Standard Pipeline</Heading>
              <Text fontSize="xs" color="gray.500">Single query with retry</Text>
            </Box>
          </HStack>
          
          <VStack align="stretch" spacing={4}>
            <PipelineStep number="1" title="Parse Question" description="Classify intent and extract entities" />
            <PipelineStep number="2" title="Generate SQL" description="LLM creates query from schema context" />
            <PipelineStep number="3" title="Validate" description="Enforce SELECT-only, check tables/columns" />
            <PipelineStep number="4" title="Execute" description="Run against Postgres database" />
            <PipelineStep number="5" title="Synthesize" description="Generate natural language answer" />
          </VStack>
        </Box>

        {/* Multi-Query Pipeline */}
        <Box
          p={6}
          borderWidth="2px"
          borderColor="purple.200"
          borderRadius="xl"
          bgGradient="linear(to-br, purple.50, white)"
          shadow="sm"
        >
          <HStack mb={5} spacing={2}>
            <Box p={2} bg="purple.100" borderRadius="lg">
              <SparklesIcon boxSize={5} color="purple.600" />
            </Box>
            <Box>
              <HStack spacing={2}>
                <Heading size="sm" color="gray.800">Multi-Query Pipeline</Heading>
                <Badge colorScheme="purple" variant="solid" fontSize="xs">NEW</Badge>
              </HStack>
              <Text fontSize="xs" color="gray.500">3 diverse queries with synthesis</Text>
            </Box>
          </HStack>
          
          <VStack align="stretch" spacing={4}>
            <PipelineStep number="1" title="Generate 3 Queries" description="Different table/logic approaches" color="purple" />
            <PipelineStep number="2" title="Parallel Execution" description="10s timeout per query" color="purple" />
            <PipelineStep number="3" title="Cross-Reference" description="Compare results for consensus" color="purple" />
            <PipelineStep number="4" title="Synthesize Best" description="Pick most reliable answer" color="purple" />
          </VStack>
        </Box>
      </SimpleGrid>

      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
        {/* Data Sources */}
        <Box p={5} borderWidth="1px" borderRadius="xl" bg="white" shadow="sm">
          <HStack mb={4} spacing={2}>
            <DatabaseIcon boxSize={5} color="teal.500" />
            <Heading size="sm" color="gray.700">Data Sources</Heading>
          </HStack>
          <VStack align="stretch" spacing={2}>
            <HStack p={3} bg="gray.50" borderRadius="lg" justify="space-between">
              <Code bg="teal.100" color="teal.800">matches</Code>
              <Text fontSize="sm" color="gray.600">25 seasons of EPL results</Text>
            </HStack>
            <HStack p={3} bg="gray.50" borderRadius="lg" justify="space-between">
              <Code bg="teal.100" color="teal.800">player_stats</Code>
              <Text fontSize="sm" color="gray.600">FBref player statistics</Text>
            </HStack>
            <HStack p={3} bg="gray.50" borderRadius="lg" justify="space-between">
              <Code bg="teal.100" color="teal.800">v_team_*_streaks</Code>
              <Text fontSize="sm" color="gray.600">7 precomputed streak views</Text>
            </HStack>
          </VStack>
        </Box>

        {/* Robustness */}
        <Box p={5} borderWidth="1px" borderRadius="xl" bg="white" shadow="sm">
          <HStack mb={4} spacing={2}>
            <ShieldIcon boxSize={5} color="green.500" />
            <Heading size="sm" color="gray.700">Safety & Robustness</Heading>
          </HStack>
          <VStack align="stretch" spacing={2}>
            <HStack p={3} bg="green.50" borderRadius="lg">
              <Badge colorScheme="green" variant="subtle">✓</Badge>
              <Text fontSize="sm" color="gray.700">SELECT-only enforcement</Text>
            </HStack>
            <HStack p={3} bg="green.50" borderRadius="lg">
              <Badge colorScheme="green" variant="subtle">✓</Badge>
              <Text fontSize="sm" color="gray.700">Table/column allowlist validation</Text>
            </HStack>
            <HStack p={3} bg="green.50" borderRadius="lg">
              <Badge colorScheme="green" variant="subtle">✓</Badge>
              <Text fontSize="sm" color="gray.700">CTE and complex query support</Text>
            </HStack>
            <HStack p={3} bg="green.50" borderRadius="lg">
              <Badge colorScheme="green" variant="subtle">✓</Badge>
              <Text fontSize="sm" color="gray.700">Team name normalization</Text>
            </HStack>
          </VStack>
        </Box>
      </SimpleGrid>
    </Box>
  );
}
