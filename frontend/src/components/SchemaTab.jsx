import React, { useMemo } from 'react';
import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Badge,
  Box,
  Code,
  HStack,
  Icon,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  Text,
  VStack,
} from '@chakra-ui/react';

const TableIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M3 3h18v18H3V3zm16 4V5H5v2h14zm0 4v-2H5v2h14zm0 4v-2H5v2h14zm0 4v-2H5v2h14z"/>
  </Icon>
);

const ViewIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
  </Icon>
);

export default function SchemaTab({ schema }) {
  const relations = useMemo(() => schema?.relations || [], [schema]);

  const tables = relations.filter(r => r.type === 'table');
  const views = relations.filter(r => r.type === 'view');

  return (
    <Box>
      <Text color="gray.600" mb={6} fontSize="md">
        Browse the database schema below. Click on any table or view to see its columns and details.
      </Text>

      {tables.length > 0 && (
        <Box mb={8}>
          <HStack mb={4} spacing={2}>
            <TableIcon boxSize={5} color="blue.500" />
            <Text fontWeight="semibold" fontSize="lg" color="gray.700">
              Tables ({tables.length})
            </Text>
          </HStack>
          <Accordion allowMultiple>
            {tables.map((rel) => (
              <SchemaAccordionItem key={`${rel.schema}.${rel.name}`} rel={rel} />
            ))}
          </Accordion>
        </Box>
      )}

      {views.length > 0 && (
        <Box>
          <HStack mb={4} spacing={2}>
            <ViewIcon boxSize={5} color="teal.500" />
            <Text fontWeight="semibold" fontSize="lg" color="gray.700">
              Views ({views.length})
            </Text>
          </HStack>
          <Accordion allowMultiple>
            {views.map((rel) => (
              <SchemaAccordionItem key={`${rel.schema}.${rel.name}`} rel={rel} />
            ))}
          </Accordion>
        </Box>
      )}
    </Box>
  );
}

function SchemaAccordionItem({ rel }) {
  const title = `${rel.schema}.${rel.name}`;
  const isView = rel.type === 'view';
  
  return (
    <AccordionItem
      borderWidth="1px"
      borderRadius="lg"
      mb={2}
      overflow="hidden"
      _hover={{ shadow: 'sm' }}
      transition="shadow 0.2s"
    >
      <h2>
        <AccordionButton py={4} _expanded={{ bg: isView ? 'teal.50' : 'blue.50' }}>
          <Box flex="1" textAlign="left">
            <HStack gap={3}>
              <Code
                bg={isView ? 'teal.100' : 'blue.100'}
                color={isView ? 'teal.800' : 'blue.800'}
                px={3}
                py={1}
                borderRadius="md"
                fontWeight="semibold"
              >
                {title}
              </Code>
              {typeof rel.row_estimate === 'number' && (
                <Badge variant="subtle" colorScheme="gray" fontSize="xs">
                  ~{rel.row_estimate.toLocaleString()} rows
                </Badge>
              )}
              <Badge colorScheme="gray" variant="outline" fontSize="xs">
                {(rel.columns || []).length} columns
              </Badge>
            </HStack>
          </Box>
          <AccordionIcon />
        </AccordionButton>
      </h2>
      <AccordionPanel pb={4} bg="gray.50">
        <Box overflowX="auto" borderWidth="1px" borderRadius="lg" bg="white">
          <Table size="sm" variant="simple">
            <Thead bg="gray.100">
              <Tr>
                <Th color="gray.600" fontSize="xs">Column</Th>
                <Th color="gray.600" fontSize="xs">Type</Th>
                <Th color="gray.600" fontSize="xs">Nullable</Th>
              </Tr>
            </Thead>
            <Tbody>
              {(rel.columns || []).map((c) => (
                <Tr key={`${title}.${c.name}`} _hover={{ bg: 'gray.50' }}>
                  <Td>
                    <Code bg="gray.100" fontSize="sm">{c.name}</Code>
                  </Td>
                  <Td>
                    <Text fontSize="sm" color="gray.600">{c.type}</Text>
                  </Td>
                  <Td>
                    <Badge
                      colorScheme={c.not_null ? 'red' : 'green'}
                      variant="subtle"
                      fontSize="xs"
                    >
                      {c.not_null ? 'NOT NULL' : 'nullable'}
                    </Badge>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>

        {rel.definition && (
          <Box mt={4}>
            <Text fontWeight="semibold" mb={2} color="gray.700" fontSize="sm">
              View Definition
            </Text>
            <Box
              borderRadius="lg"
              p={4}
              overflowX="auto"
              bg="gray.900"
            >
              <Code
                whiteSpace="pre"
                display="block"
                bg="transparent"
                color="green.300"
                fontSize="sm"
              >
                {rel.definition}
              </Code>
            </Box>
          </Box>
        )}
      </AccordionPanel>
    </AccordionItem>
  );
}
