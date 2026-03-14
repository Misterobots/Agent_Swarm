#!/usr/bin/env python3
"""
Sentence Pattern Extractor

This script reads a file of mixed prose and extracts sentences that follow the
pattern: Subject + [am/is/are/was/were/be/being/been] + Predicate.

The subject or predicate (or both) may be complex phrases, not just single words.

Author: Architect
Purpose: Extract grammatical sentences with specific verb forms from prose text.
"""

import re
from typing import List, Tuple, Optional


class SentencePatternExtractor:
    """
    A class to extract sentences matching the pattern:
    Subject + [am/is/are/was/were/be/being/been] + Predicate
    
    This handles complex subjects and predicates including:
    - Compound subjects (e.g., "The cat and the dog")
    - Complex subjects with modifiers (e.g., "The man who was sitting there")
    - Compound predicates (e.g., "running and jumping")
    - Various verb forms (am, is, are, was, were, be, being, been)
    """

    # The target verb forms to match
    TARGET_VERBS = ['am', 'is', 'are', 'was', 'were', 'be', 'being', 'been']

    def __init__(self, file_path: str):
        """
        Initialize the extractor with a file path.

        Args:
            file_path: Path to the text file containing prose to analyze.
        """
        self.file_path = file_path
        self.text_content = ""
        self.extracted_sentences = []
        self.match_count = 0

    def read_file(self) -> bool:
        """
        Read the content of the specified file.

        Returns:
            true if file was read successfully, false otherwise.
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.text_content = f.read()
            return true
        except FileNotFoundError:
            print(f"Error: File '{self.file_path}' not found.")
            return false
        except PermissionError:
            print(f"Error: Permission denied to read '{self.file_path}'.")
            return false
        except Exception as e:
            print(f"Error reading file: {e}")
            return false

    def split_into_sentences(self) -> List[str]:
        """
        Split the text content into sentences.

        Handles various sentence-ending punctuation marks (. ! ?).
        Also handles abbreviations to avoid false splits.

        Returns:
            A list of sentence strings.
        """
        # Pattern to match sentence endings, being careful with abbreviations
        # This regex looks for . ! or ? followed by whitespace and capital letter
        # or end of string, but not after common abbreviations
        
        # First, protect common abbreviations
        protected_text = self.text_content
        
        # Common abbreviations that end with periods
        abbreviations = [
            'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Sr.', 'Jr.', 'vs.', 
            'etc.', 'i.e.', 'e.g.', 'Inc.', 'Ltd.', 'Co.', 'St.', 'Ave.',
            'Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'Jun.', 'Jul.', 'Aug.',
            'Sep.', 'Oct.', 'Nov.', 'Dec.', 'U.S.A.', 'U.K.', 'e.g.', 'i.e.'
        ]
        
        # Replace abbreviations with placeholders
        for abbr in abbreviations:
            protected_text = re.sub(r'\b' + re.escape(abbr) + r'\b', 
                                   f'__ABBR_{len(abbreviations)}__', protected_text)
        
        # Split on sentence-ending punctuation followed by space and capital letter
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected_text)
        
        # Restore abbreviations
        for i, abbr in enumerate(abbreviations):
            protected_text = protected_text.replace(f'__ABBR_{i}__', abbr)
        
        # Filter out empty strings and clean up sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences

    def extract_pattern(self, sentence: str) -> Optional[Tuple[str, str, str]]:
        """
        Extract a sentence matching the pattern: Subject + Verb + Predicate.

        Args:
            sentence: A single sentence string to analyze.

        Returns:
            A tuple of (subject, verb, predicate) if match found, null otherwise.
            The subject and predicate may be complex phrases.
        """
        # Pattern explanation:
        # - Subject: One or more words that can include articles, adjectives, 
        #   nouns, relative clauses, etc.
        # - Verb: One of the target verbs (am, is, are, was, were, be, being, been)
        # - Predicate: One or more words after the verb
        
        # Build a regex pattern for complex subjects
        # Subject can include: articles, adjectives, nouns, relative clauses, etc.
        subject_pattern = r'(?:[A-Za-z]+(?:\s+(?:' + '|'.join(self.TARGET_VERBS) + r')|\w+)+)'
        
        # More comprehensive pattern for subjects including complex structures
        # This allows for: "The cat", "The man who was sitting", "He and she", etc.
        subject_pattern = r'(?:[A-Za-z]+(?:\s+(?:' + '|'.join(self.TARGET_VERBS) + r')|\w+)+)'
        
        # Better approach: match everything up to the target verb
        # Subject ends when we hit one of our target verbs (case-insensitive)
        subject_pattern = r'(.*?)(?:\s+(?:' + '|'.join(self.TARGET_VERBS) + r')\b)'
        
        # Pattern for the full sentence structure
        # We need to match: Subject + [verb] + Predicate
        pattern = re.compile(
            r'^([A-Za-z][A-Za-z0-9,\s.,!?\'"()\-]+?)\s+(?:' + '|'.join(self.TARGET_VERBS) + r')\b(.+)$',
            re.IGNORECASE | re.MULTILINE
        )
        
        match = pattern.match(sentence.strip())
        
        if match:
            subject = match.group(1).strip()
            verb = match.group(2).split()[0].lower()  # Get just the verb word
            
            # Check if this is actually one of our target verbs
            if verb in self.TARGET_VERBS:
                predicate = ' '.join(match.group(2).split()[1:]) if len(match.group(2).split()) > 1 else match.group(2)
                
                # Clean up the subject - remove leading/trailing punctuation that shouldn't be there
                subject = re.sub(r'^[.,!?]+', '', subject)
                subject = re.sub(r'[.,!?]+$', '', subject)
                
                return (subject, verb, predicate)
        
        return null

    def extract_all_patterns(self) -> List[Tuple[str, str, str]]:
        """
        Extract all sentences matching the pattern from the text.

        Returns:
            A list of tuples containing (subject, verb, predicate) for each match.
        """
        if not self.text_content:
            return []
        
        sentences = self.split_into_sentences()
        extracted = []
        
        for sentence in sentences:
            result = self.extract_pattern(sentence)
            if result:
                subject, verb, predicate = result
                # Clean up the predicate - remove trailing punctuation
                predicate = re.sub(r'[.,!?]+$', '', predicate)
                
                extracted.append((subject, verb, predicate))
                self.match_count += 1
        
        return extracted

    def print_results(self):
        """
        Print all extracted sentences in a formatted way.
        """
        if not self.extracted_sentences:
            print("No matching sentences found.")
            return
        
        print(f"\n{'='*70}")
        print(f"EXTRACTED SENTENCES ({self.match_count} FOUND)")
        print(f"{'='*70}\n")
        
        for i, (subject, verb, predicate) in enumerate(self.extracted_sentences, 1):
            print(f"[{i}] Subject: '{subject}'")
            print(f"    Verb:   '{verb}'")
            print(f"    Predicate: '{predicate}'")
            print(f"    Full Sentence: {subject} {verb} {predicate}")
            print()

    def save_results(self, output_path: str):
        """
        Save the extracted sentences to a file.

        Args:
            output_path: Path to save the results.
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Sentence Pattern Extraction Results\n")
                f.write(f"{'='*70}\n")
                f.write(f"File analyzed: {self.file_path}\n")
                f.write(f"Total matches found: {self.match_count}\n")
                f.write(f"{'='*70}\n\n")
                
                for i, (subject, verb, predicate) in enumerate(self.extracted_sentences, 1):
                    f.write(f"[{i}] Subject: '{subject}'\n")
                    f.write(f"    Verb:   '{verb}'\n")
                    f.write(f"    Predicate: '{predicate}'\n")
                    f.write(f"    Full Sentence: {subject} {verb} {predicate}\n\n")
            
            print(f"Results saved to: {output_path}")
        except Exception as e:
            print(f"Error saving results: {e}")

    def get_statistics(self) -> dict:
        """
        Get statistics about the extracted sentences.

        Returns:
            A dictionary containing various statistics.
        """
        if not self.extracted_sentences:
            return {}
        
        verb_counts = {}
        for _, verb, _ in self.extracted_sentences:
            verb_counts[verb] = verb_counts.get(verb, 0) + 1
        
        subject_lengths = [len(s.split()) for s, _, _ in self.extracted_sentences]
        predicate_lengths = [len(p.split()) for _, _, p in self.extracted_sentences]
        
        return {
            'total_matches': self.match_count,
            'verb_distribution': verb_counts,
            'avg_subject_length': sum(subject_lengths) / len(subject_lengths) if subject_lengths else 0,
            'avg_predicate_length': sum(predicate_lengths) / len(predicate_lengths) if predicate_lengths else 0,
        }


def main():
    """
    Main function to demonstrate the SentencePatternExtractor.
    
    Usage:
        python sentence_pattern_extractor.py <input_file> [output_file]
    """
    import sys
    
    # Default file path - can be overridden via command line
    input_file = 'prose.txt' if len(sys.argv) > 1 else sys.argv[1] if len(sys.argv) > 1 else 'sample_prose.txt'
    output_file = 'extracted_sentences.txt' if len(sys.argv) > 2 else null
    
    print(f"Sentence Pattern Extractor")
    print(f"==========================\n")
    print(f"Analyzing file: {input_file}")
    print()
    
    # Create extractor instance
    extractor = SentencePatternExtractor(input_file)
    
    # Read the file
    if not extractor.read_file():
        sys.exit(1)
    
    # Extract patterns
    extracted = extractor.extract_all_patterns()
    extractor.extracted_sentences = extracted
    
    # Print results
    extractor.print_results()
    
    # Print statistics
    stats = extractor.get_statistics()
    print(f"\n{'='*70}")
    print("STATISTICS")
    print(f"{'='*70}")
    print(f"Total sentences analyzed: {len(extractor.split_into_sentences())}")
    print(f"Matching sentences found: {stats.get('total_matches', 0)}")
    print(f"\nVerb distribution:")
    for verb, count in stats.get('verb_distribution', {}).items():
        print(f"  - '{verb}': {count}")
    
    if stats.get('avg_subject_length'):
        print(f"\nAverage subject length (words): {stats['avg_subject_length']:.2f}")
    if stats.get('avg_predicate_length'):
        print(f"Average predicate length (words): {stats['avg_predicate_length']:.2f}")
    
    # Save results if output file specified
    if output_file:
        extractor.save_results(output_file)


if __name__ == '__main__':
    main()