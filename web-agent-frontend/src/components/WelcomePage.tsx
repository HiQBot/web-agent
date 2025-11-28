import React, { useEffect } from 'react';
import { motion } from 'framer-motion';

interface WelcomePageProps {
  onEnter: () => void;
}

const WelcomePage: React.FC<WelcomePageProps> = ({ onEnter }) => {
  // Handle scroll to navigate to dashboard
  useEffect(() => {
    let scrollTimeout: NodeJS.Timeout;
    let hasScrolled = false;

    const handleScroll = (e: WheelEvent) => {
      // Only trigger on downward scroll
      if (e.deltaY > 0 && !hasScrolled) {
        hasScrolled = true;
        
        // Small delay to show scroll animation
        scrollTimeout = setTimeout(() => {
          onEnter();
        }, 300);
      }
    };

    // Also handle touch swipe down
    let touchStartY = 0;
    const handleTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0].clientY;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!hasScrolled && touchStartY > 0) {
        const touchEndY = e.touches[0].clientY;
        const deltaY = touchEndY - touchStartY;
        
        // Swipe down detected
        if (deltaY > 50) {
          hasScrolled = true;
          scrollTimeout = setTimeout(() => {
            onEnter();
          }, 300);
        }
      }
    };

    window.addEventListener('wheel', handleScroll, { passive: true });
    window.addEventListener('touchstart', handleTouchStart, { passive: true });
    window.addEventListener('touchmove', handleTouchMove, { passive: true });

    return () => {
      clearTimeout(scrollTimeout);
      window.removeEventListener('wheel', handleScroll);
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
    };
  }, [onEnter]);
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2,
        delayChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: [0.22, 1, 0.36, 1] as const, // Custom easing for smooth animation
      },
    },
  };

  const featurePillVariants = {
    hidden: { opacity: 0, scale: 0.8 },
    visible: (i: number) => ({
      opacity: 1,
      scale: 1,
      transition: {
        delay: i * 0.1,
        duration: 0.4,
        type: "spring" as const,
        stiffness: 200,
      },
    }),
    hover: {
      scale: 1.05,
      y: -2,
      transition: { duration: 0.2 },
    },
  };

  return (
    <motion.div
      className="absolute inset-0 bg-gradient-to-br from-gray-900 via-slate-900 to-gray-900 flex items-center justify-center p-8 overflow-hidden z-50"
      initial="hidden"
      animate="visible"
      variants={containerVariants}
    >
      {/* Animated Background Orbs with Framer Motion */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 50, 0],
            y: [0, -30, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0,
          }}
        />
        <motion.div
          className="absolute top-1/2 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 50, 0],
            y: [0, -30, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 2,
          }}
        />
        <motion.div
          className="absolute bottom-1/4 left-1/2 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 50, 0],
            y: [0, -30, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 4,
          }}
        />
      </div>

      {/* Animated Grid Pattern */}
      <motion.div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '50px 50px',
        }}
        animate={{
          backgroundPosition: ['0px 0px', '50px 50px'],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: 'linear',
        }}
      />

      <motion.div
        className="text-center max-w-4xl relative z-10"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Main Title with Split Animation */}
        <motion.h1
          className="mt-6 text-5xl sm:text-6xl md:text-7xl font-black text-white"
          variants={itemVariants}
        >
          <motion.span
            className="block bg-gradient-to-r from-white via-cyan-200 to-blue-300 bg-clip-text text-transparent"
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
          >
            HiQBot
          </motion.span>
          <motion.span
            className="block bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent"
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
          >
            Web Agent
          </motion.span>
        </motion.h1>

        {/* Subtitle with Word-by-Word Animation */}
        <motion.p
          className="mt-8 text-lg sm:text-xl text-gray-300 max-w-2xl mx-auto"
          variants={itemVariants}
        >
          The next-generation platform for{' '}
          <motion.span
            className="text-cyan-400 font-semibold"
            whileHover={{ scale: 1.1, color: '#67e8f9' }}
            transition={{ type: "spring", stiffness: 400 }}
          >
            real-time
          </motion.span>
          ,{' '}
          <motion.span
            className="text-blue-400 font-semibold"
            whileHover={{ scale: 1.1, color: '#60a5fa' }}
            transition={{ type: "spring", stiffness: 400 }}
          >
            AI-powered
          </motion.span>{' '}
          test generation and execution.
        </motion.p>

        {/* Feature Pills with Stagger Animation */}
        <motion.div
          className="mt-10 flex flex-wrap justify-center gap-3"
          variants={itemVariants}
        >
          {[
            { text: '🤖 AI-Powered', color: 'cyan' },
            { text: '⚡ Real-Time', color: 'blue' },
            { text: '🚀 Automated', color: 'purple' },
          ].map((feature, i) => (
            <motion.span
              key={i}
              custom={i}
              variants={featurePillVariants}
              initial="hidden"
              animate="visible"
              whileHover="hover"
              className={`px-4 py-2 glass rounded-full text-sm text-${feature.color}-300 border border-${feature.color}-400/30 cursor-pointer`}
            >
              {feature.text}
            </motion.span>
          ))}
        </motion.div>

        {/* Enhanced CTA Button */}
        <motion.div
          className="mt-12"
          variants={itemVariants}
        >
          <motion.button
            onClick={onEnter}
            className="group relative inline-flex items-center justify-center px-12 py-5 text-lg font-bold rounded-xl text-gray-900 bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 shadow-2xl shadow-cyan-500/30 overflow-hidden"
            whileHover={{
              scale: 1.05,
              boxShadow: '0 20px 40px rgba(6, 182, 212, 0.4)',
            }}
            whileTap={{ scale: 0.95 }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.6 }}
          >
            {/* Animated Shimmer Effect */}
            <motion.span
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
              initial={{ x: '-100%' }}
              animate={{
                x: ['-100%', '200%'],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                repeatDelay: 1,
                ease: 'linear',
              }}
            />

            <motion.span
              className="relative flex items-center gap-2"
              whileHover={{ x: 5 }}
            >
              Enter Dashboard
              <motion.svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                whileHover={{ x: 5 }}
                transition={{ type: "spring", stiffness: 400 }}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M9 5l7 7-7 7"
                />
              </motion.svg>
            </motion.span>
          </motion.button>
        </motion.div>

        {/* Scroll Indicator with Bounce */}
        <motion.div
          className="mt-16 cursor-pointer"
          variants={itemVariants}
          onClick={onEnter}
        >
          <motion.div
            className="flex flex-col items-center gap-2 text-gray-400 text-sm hover:text-cyan-400 transition-colors"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.1 }}
            whileHover={{ scale: 1.1 }}
          >
            <motion.span
              animate={{
                opacity: [0.6, 1, 0.6],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              Scroll to explore
            </motion.span>
            <motion.svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              animate={{
                y: [0, 10, 0],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 14l-7 7m0 0l-7-7m7 7V3"
              />
            </motion.svg>
          </motion.div>
        </motion.div>
      </motion.div>
    </motion.div>
  );
};

export default WelcomePage;
